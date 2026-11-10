terraform {
  backend "s3" {
    bucket       = "devncloudtechdevopsrrrr"
    key          = "terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
