resource "aws_cognito_user_pool" "main" {
  name              = local.name
  mfa_configuration = "ON"
  software_token_mfa_configuration { enabled = true }
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  admin_create_user_config { allow_admin_create_user_only = true }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 3
  }
  deletion_protection = var.environment == "production" ? "ACTIVE" : "INACTIVE"
}
resource "aws_cognito_user_pool_client" "alb" {
  name                                 = "${local.name}-alb"
  user_pool_id                         = aws_cognito_user_pool.main.id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  callback_urls                        = var.callback_urls
  logout_urls                          = var.logout_urls
  supported_identity_providers         = ["COGNITO"]
  enable_token_revocation              = true
  prevent_user_existence_errors        = "ENABLED"
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
resource "aws_cognito_user_pool_domain" "main" {
  domain       = var.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.main.id
}

data "aws_iam_policy_document" "plan_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:pull_request"]
    }
  }
}
resource "aws_iam_role" "github_plan" {
  name                 = "${local.name}-github-plan"
  assume_role_policy   = data.aws_iam_policy_document.plan_assume.json
  max_session_duration = 3600
}
data "aws_iam_policy_document" "plan_read" {
  statement {
    effect    = "Allow"
    actions   = ["acm:DescribeCertificate", "acm:ListCertificates", "budgets:ViewBudget", "cognito-idp:Describe*", "cognito-idp:List*", "ec2:Describe*", "ecr:Describe*", "ecr:GetLifecyclePolicy", "ecs:Describe*", "ecs:List*", "elasticloadbalancing:Describe*", "iam:Get*", "iam:List*", "kms:DescribeKey", "kms:ListAliases", "logs:Describe*", "rds:Describe*", "s3:GetBucket*", "s3:ListAllMyBuckets", "s3:ListBucket", "secretsmanager:DescribeSecret", "sns:GetTopicAttributes", "sns:List*", "wafv2:Get*", "wafv2:List*"]
    resources = ["*"]
  }
}
resource "aws_iam_role_policy" "github_plan" {
  name   = "read-only-plan"
  role   = aws_iam_role.github_plan.id
  policy = data.aws_iam_policy_document.plan_read.json
}
