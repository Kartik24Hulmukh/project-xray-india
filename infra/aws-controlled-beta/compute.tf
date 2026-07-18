resource "aws_ecr_repository" "app" {
  name                 = local.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.custody.arn
  }
}

resource "aws_ecs_cluster" "main" {
  name = local.name
  setting { name = "containerInsights"
 value = "enabled" }
}
resource "aws_cloudwatch_log_group" "app" { name = "/ecs/${local.name}/app"
 retention_in_days = 30 }
resource "aws_cloudwatch_log_group" "gateway" { name = "/ecs/${local.name}/gateway"
 retention_in_days = 30 }
resource "aws_service_discovery_private_dns_namespace" "main" { name = "${local.name}.internal"
 vpc = aws_vpc.main.id }
resource "aws_service_discovery_service" "app" {
  name = "app"
  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records { ttl = 10
 type = "A" }
    routing_policy = "MULTIVALUE"
  }
  health_check_custom_config { failure_threshold = 1 }
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRole"]
    principals { type = "Service"
 identifiers = ["ecs-tasks.amazonaws.com"] }
  }
}
resource "aws_iam_role" "app_execution" { name = "${local.name}-app-execution"
 assume_role_policy = data.aws_iam_policy_document.ecs_assume.json }
resource "aws_iam_role" "gateway_execution" { name = "${local.name}-gateway-execution"
 assume_role_policy = data.aws_iam_policy_document.ecs_assume.json }
resource "aws_iam_role_policy_attachment" "app_execution" { role = aws_iam_role.app_execution.name
 policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" }
resource "aws_iam_role_policy_attachment" "gateway_execution" { role = aws_iam_role.gateway_execution.name
 policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" }

data "aws_iam_policy_document" "app_execution_secrets" {
  statement {
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = concat(values(var.app_secret_arns), aws_db_instance.main.master_user_secret[*].secret_arn)
  }
  statement { effect = "Allow"
 actions = ["kms:Decrypt"]
 resources = [aws_kms_key.database.arn] }
}
resource "aws_iam_role_policy" "app_execution_secrets" { name = "secrets"
 role = aws_iam_role.app_execution.id
 policy = data.aws_iam_policy_document.app_execution_secrets.json }

data "aws_iam_policy_document" "gateway_execution_secrets" {
  statement {
    effect = "Allow"
    actions = ["secretsmanager:GetSecretValue"]
    resources = [var.app_secret_arns.oidc_proxy_secret, var.gateway_role_bindings_secret_arn]
  }
}
resource "aws_iam_role_policy" "gateway_execution_secrets" { name = "secrets"
 role = aws_iam_role.gateway_execution.id
 policy = data.aws_iam_policy_document.gateway_execution_secrets.json }

resource "aws_iam_role" "app_task" { name = "${local.name}-app-task"
 assume_role_policy = data.aws_iam_policy_document.ecs_assume.json }
resource "aws_iam_role" "gateway_task" { name = "${local.name}-gateway-task"
 assume_role_policy = data.aws_iam_policy_document.ecs_assume.json }
data "aws_iam_policy_document" "app_task" {
  statement {
    effect = "Allow"
    actions = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = ["${aws_s3_bucket.custody["evidence-private"].arn}/*"]
  }
  statement {
    effect = "Allow"
    actions = ["s3:ListBucket"]
    resources = [aws_s3_bucket.custody["evidence-private"].arn]
  }
  statement {
    effect = "Allow"
    actions = ["kms:Decrypt"]
    resources = [aws_kms_key.custody.arn]
  }
}
resource "aws_iam_role_policy" "app_task" { name = "evidence-read"
 role = aws_iam_role.app_task.id
 policy = data.aws_iam_policy_document.app_task.json }

resource "aws_lb" "main" {
  name                       = substr(local.name, 0, 32)
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = values(aws_subnet.app)[*].id
  enable_deletion_protection = true
  drop_invalid_header_fields = true
}
resource "aws_lb_target_group" "gateway" {
  name                 = substr("${local.name}-gw", 0, 32)
  port                 = 8080
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  target_type          = "ip"
  deregistration_delay = 30
  health_check {
    enabled = true
    path = "/health"
    matcher = "200"
    interval = 30
    timeout = 5
    healthy_threshold = 2
    unhealthy_threshold = 3
  }
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port = 80
  protocol = "HTTP"
  default_action {
    type = "redirect"
    redirect { port = "443"
 protocol = "HTTPS"
 status_code = "HTTP_301" }
  }
}
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port = 443
  protocol = "HTTPS"
  certificate_arn = var.certificate_arn
  ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  default_action {
    type = "authenticate-cognito"
    order = 1
    authenticate_cognito {
      user_pool_arn = aws_cognito_user_pool.main.arn
      user_pool_client_id = aws_cognito_user_pool_client.alb.id
      user_pool_domain = aws_cognito_user_pool_domain.main.domain
      on_unauthenticated_request = "authenticate"
      session_timeout = 3600
    }
  }
  default_action { type = "forward"
 order = 2
 target_group_arn = aws_lb_target_group.gateway.arn }
}

locals {
  image = "${aws_ecr_repository.app.repository_url}@${var.image_digest}"
  cognito_issuer = join("", ["https://cognito-idp.", var.aws_region, ".amazonaws.com/", aws_cognito_user_pool.main.id])
  app_environment = [
    { name = "APP_ENV", value = "production" },
    { name = "PORT", value = "8081" },
    { name = "PUBLIC_BASE_URL", value = join("", ["https://", var.domain_name]) },
    { name = "OBJECT_STORAGE_MODE", value = "managed" },
    { name = "STORAGE_BUCKET", value = aws_s3_bucket.custody["evidence-private"].id },
    { name = "STORAGE_REGION", value = var.aws_region },
    { name = "GATEWAY_ASSERTION_VERSION", value = "1" },
    { name = "GATEWAY_ASSERTION_AUDIENCE", value = "project-xray-app" },
    { name = "GATEWAY_ASSERTION_ISSUERS", value = local.cognito_issuer },
    { name = "GATEWAY_ASSERTION_KEY_ID", value = "gateway-${var.environment}-v1" },
    { name = "DB_HOST", value = aws_db_instance.main.address },
    { name = "DB_PORT", value = tostring(aws_db_instance.main.port) },
    { name = "DB_NAME", value = var.db_name },
    { name = "DB_SSLMODE", value = "require" }
  ]
  app_secrets = [
    { name = "TOKEN_PEPPER", valueFrom = var.app_secret_arns.token_pepper },
    { name = "AUDIT_HMAC_KEY", valueFrom = var.app_secret_arns.audit_hmac_key },
    { name = "BACKUP_HMAC_KEY", valueFrom = var.app_secret_arns.backup_hmac_key },
    { name = "OIDC_PROXY_SECRET", valueFrom = var.app_secret_arns.oidc_proxy_secret },
    { name = "MONITORING_WEBHOOK_URL", valueFrom = var.app_secret_arns.monitoring_webhook_url },
    { name = "MONITORING_WEBHOOK_SECRET", valueFrom = var.app_secret_arns.monitoring_webhook_secret },
    { name = "DB_USERNAME", valueFrom = "${aws_db_instance.main.master_user_secret[0].secret_arn}:username::" },
    { name = "DB_PASSWORD", valueFrom = "${aws_db_instance.main.master_user_secret[0].secret_arn}:password::" }
  ]
}

resource "aws_ecs_task_definition" "app" {
  family = "${local.name}-app"
  requires_compatibilities = ["FARGATE"]
  network_mode = "awsvpc"
  cpu = 512
  memory = 1024
  execution_role_arn = aws_iam_role.app_execution.arn
  task_role_arn = aws_iam_role.app_task.arn
  runtime_platform { operating_system_family = "LINUX"
 cpu_architecture = "X86_64" }
  container_definitions = jsonencode([{
    name = "app"
    image = local.image
    essential = true
    command = ["python3", "app/server.py"]
    user = "10001"
    readonlyRootFilesystem = true
    environment = local.app_environment
    secrets = local.app_secrets
    portMappings = [{ containerPort = 8081, hostPort = 8081, protocol = "tcp" }]
    healthCheck = { command = ["CMD-SHELL", "python3 -c \"import urllib.request
 urllib.request.urlopen('http://127.0.0.1:8081/health')\""], interval = 30, timeout = 5, retries = 3, startPeriod = 20 }
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.app.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "app" } }
    linuxParameters = { capabilities = { drop = ["ALL"] } }
  }])
}

resource "aws_ecs_task_definition" "gateway" {
  family = "${local.name}-gateway"
  requires_compatibilities = ["FARGATE"]
  network_mode = "awsvpc"
  cpu = 256
  memory = 512
  execution_role_arn = aws_iam_role.gateway_execution.arn
  task_role_arn = aws_iam_role.gateway_task.arn
  runtime_platform { operating_system_family = "LINUX"
 cpu_architecture = "X86_64" }
  container_definitions = jsonencode([{
    name = "gateway"
    image = local.image
    essential = true
    command = ["python3", "app/alb_gateway.py"]
    user = "10001"
    readonlyRootFilesystem = true
    environment = [
      { name = "GATEWAY_PORT", value = "8080" },
      { name = "APP_UPSTREAM", value = join("", ["http://app.", aws_service_discovery_private_dns_namespace.main.name, ":8081"]) },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "ALB_SIGNER_ARN", value = aws_lb.main.arn },
      { name = "COGNITO_CLIENT_ID", value = aws_cognito_user_pool_client.alb.id },
      { name = "COGNITO_ISSUER", value = local.cognito_issuer },
      { name = "GATEWAY_ASSERTION_KEY_ID", value = "gateway-${var.environment}-v1" },
      { name = "GATEWAY_ASSERTION_AUDIENCE", value = "project-xray-app" }
    ]
    secrets = [
      { name = "OIDC_PROXY_SECRET", valueFrom = var.app_secret_arns.oidc_proxy_secret },
      { name = "GATEWAY_ROLE_BINDINGS_JSON", valueFrom = var.gateway_role_bindings_secret_arn }
    ]
    portMappings = [{ containerPort = 8080, hostPort = 8080, protocol = "tcp" }]
    healthCheck = { command = ["CMD-SHELL", "python3 -c \"import urllib.request
 urllib.request.urlopen('http://127.0.0.1:8080/health')\""], interval = 30, timeout = 5, retries = 3, startPeriod = 20 }
    logConfiguration = { logDriver = "awslogs", options = { "awslogs-group" = aws_cloudwatch_log_group.gateway.name, "awslogs-region" = var.aws_region, "awslogs-stream-prefix" = "gateway" } }
    linuxParameters = { capabilities = { drop = ["ALL"] } }
  }])
}

resource "aws_ecs_service" "app" {
  name = "${local.name}-app"
  cluster = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count = var.desired_count
  launch_type = "FARGATE"
  platform_version = "LATEST"
  enable_execute_command = false
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent = 200
  deployment_circuit_breaker { enable = true
 rollback = true }
  network_configuration {
    subnets = values(aws_subnet.app)[*].id
    security_groups = [aws_security_group.app.id]
    assign_public_ip = true
  }
  service_registries { registry_arn = aws_service_discovery_service.app.arn }
}

resource "aws_ecs_service" "gateway" {
  name = "${local.name}-gateway"
  cluster = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.gateway.arn
  desired_count = var.desired_count
  launch_type = "FARGATE"
  platform_version = "LATEST"
  enable_execute_command = false
  health_check_grace_period_seconds = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent = 200
  deployment_circuit_breaker { enable = true
 rollback = true }
  network_configuration {
    subnets = values(aws_subnet.app)[*].id
    security_groups = [aws_security_group.gateway.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.gateway.arn
    container_name = "gateway"
    container_port = 8080
  }
  depends_on = [aws_lb_listener.https, aws_ecs_service.app]
}
