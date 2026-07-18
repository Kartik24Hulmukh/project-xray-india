resource "aws_kms_key" "database" { description = "${local.name} RDS encryption"
  enable_key_rotation = true
  deletion_window_in_days = 30 }
resource "aws_db_subnet_group" "main" { name = local.name
  subnet_ids = values(aws_subnet.db)[*].id }
resource "aws_db_parameter_group" "main" {
  name = "${local.name}-postgres16"
  family = "postgres16"
  parameter { name = "rds.force_ssl"
  value = "1" }
}
resource "aws_db_instance" "main" {
  identifier = local.name
  engine = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class
  allocated_storage = 20
  max_allocated_storage = 100
  storage_type = "gp3"
  storage_encrypted = true
  kms_key_id = aws_kms_key.database.arn
  db_name = var.db_name
  username = var.db_username
  manage_master_user_password = true
  master_user_secret_kms_key_id = aws_kms_key.database.arn
  db_subnet_group_name = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible = false
  multi_az = var.environment == "production"
  parameter_group_name = aws_db_parameter_group.main.name
  backup_retention_period = var.environment == "production" ? 14 : 7
  backup_window = "18:00-18:30"
  maintenance_window = "sun:19:00-sun:20:00"
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${local.name}-final"
  copy_tags_to_snapshot = true
  enabled_cloudwatch_logs_exports = ["postgresql","upgrade"]
  auto_minor_version_upgrade = true
  apply_immediately = false
}
