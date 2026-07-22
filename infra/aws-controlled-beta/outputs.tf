output "account_id" { value = data.aws_caller_identity.current.account_id }
output "region" { value = var.aws_region }
output "environment" { value = var.environment }
output "alb_dns_name" { value = aws_lb.main.dns_name }
output "ecr_repository_url" { value = aws_ecr_repository.app.repository_url }
output "ecs_cluster_name" { value = aws_ecs_cluster.main.name }
output "ecs_app_service_name" { value = aws_ecs_service.app.name }
output "ecs_gateway_service_name" { value = aws_ecs_service.gateway.name }
output "image_reference" { value = local.image }
output "cognito_user_pool_id" { value = aws_cognito_user_pool.main.id }
output "github_plan_role_arn" { value = aws_iam_role.github_plan.arn }
output "custody_bucket_names" { value = { for k, v in aws_s3_bucket.custody : k => v.id } }
output "rds_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}
