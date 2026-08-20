terraform {
  backend "s3" {
    bucket       = "gfgkjgkkftusddtx"
    key          = "terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
