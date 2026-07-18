locals {
  custody_buckets = toset(["intake-quarantine", "evidence-private", "dossier-restricted", "publication-staging"])
  locked_buckets  = toset(var.object_lock_enabled ? ["evidence-private", "dossier-restricted"] : [])
}
resource "aws_kms_key" "custody" { description = "${local.name} custody encryption"
  enable_key_rotation = true
  deletion_window_in_days = 30 }
resource "aws_kms_alias" "custody" { name = "alias/${local.name}-custody"
  target_key_id = aws_kms_key.custody.key_id }
resource "aws_s3_bucket" "custody" {
  for_each = local.custody_buckets
  bucket_prefix = "${local.name}-${each.key}-"
  force_destroy = false
  object_lock_enabled = contains(local.locked_buckets, each.key)
}
resource "aws_s3_bucket_public_access_block" "custody" {
  for_each = aws_s3_bucket.custody
  bucket = each.value.id
  block_public_acls = true
  block_public_policy = true
  ignore_public_acls = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_ownership_controls" "custody" { for_each = aws_s3_bucket.custody
  bucket = each.value.id
  rule { object_ownership = "BucketOwnerEnforced" } }
resource "aws_s3_bucket_versioning" "custody" { for_each = aws_s3_bucket.custody
  bucket = each.value.id
  versioning_configuration { status = "Enabled" } }
resource "aws_s3_bucket_server_side_encryption_configuration" "custody" {
  for_each = aws_s3_bucket.custody
  bucket = each.value.id
  rule { bucket_key_enabled = true
  apply_server_side_encryption_by_default { sse_algorithm = "aws:kms"
  kms_master_key_id = aws_kms_key.custody.arn } }
}
resource "aws_s3_bucket_lifecycle_configuration" "custody" {
  for_each = aws_s3_bucket.custody
  bucket = each.value.id
  rule { id = "custody-retention"
  status = "Enabled"
  filter {}
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
    noncurrent_version_expiration { noncurrent_days = 365 }
  }
  depends_on = [aws_s3_bucket_versioning.custody]
}
resource "aws_s3_bucket_object_lock_configuration" "custody" {
  for_each = { for k,v in aws_s3_bucket.custody : k => v if contains(local.locked_buckets,k) }
  bucket = each.value.id
  rule { default_retention { mode = "GOVERNANCE"
  days = 365 } }
}
data "aws_iam_policy_document" "custody" {
  for_each = aws_s3_bucket.custody
  statement { sid = "DenyInsecureTransport"
  effect = "Deny"
  principals { type = "*"
  identifiers = ["*"] }
  actions = ["s3:*"]
  resources = [each.value.arn,"${each.value.arn}/*"]
  condition { test = "Bool"
  variable = "aws:SecureTransport"
  values = ["false"] } }
}
resource "aws_s3_bucket_policy" "custody" { for_each = aws_s3_bucket.custody
  bucket = each.value.id
  policy = data.aws_iam_policy_document.custody[each.key].json
  depends_on = [aws_s3_bucket_public_access_block.custody] }
