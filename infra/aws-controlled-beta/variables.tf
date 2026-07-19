variable "aws_region" {
  type    = string
  default = "ap-south-1"
  validation {
    condition     = var.aws_region == "ap-south-1"
    error_message = "Controlled beta is locked to ap-south-1."
  }
}
variable "environment" {
  type    = string
  default = "staging"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Use staging or production."
  }
}
variable "name_prefix" {
  type    = string
  default = "project-xray"
}
variable "domain_name" { type = string }
variable "certificate_arn" { type = string }
variable "image_digest" {
  type        = string
  description = "Immutable sha256 image digest only."
  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.image_digest))
    error_message = "image_digest must be sha256:<64 lowercase hex>."
  }
}
variable "notification_email" { type = string }
variable "github_repository" {
  type        = string
  description = "ORG/REPO allowed to assume the plan-only role."
  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use ORG/REPO."
  }
}
variable "github_oidc_provider_arn" { type = string }
variable "gateway_role_bindings_secret_arn" {
  type      = string
  sensitive = true
}
variable "app_secret_arns" {
  type = object({
    token_pepper              = string
    audit_hmac_key            = string
    backup_hmac_key           = string
    oidc_proxy_secret         = string
    monitoring_webhook_url    = string
    monitoring_webhook_secret = string
  })
  sensitive = true
}
variable "budget_limit_usd" {
  type    = number
  default = 180
}
variable "desired_count" {
  type    = number
  default = 2
  validation {
    condition     = var.desired_count >= 2
    error_message = "At least two tasks are required."
  }
}
variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}
variable "db_name" {
  type    = string
  default = "xray"
}
variable "db_username" {
  type    = string
  default = "xray_admin"
}
variable "cognito_domain_prefix" { type = string }
variable "callback_urls" { type = list(string) }
variable "logout_urls" { type = list(string) }
variable "object_lock_enabled" {
  type    = bool
  default = true
}
