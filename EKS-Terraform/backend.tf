terraform {
  backend "s3" {
    bucket       = "devncloudtechdevopsrrr"
    key          = "terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
