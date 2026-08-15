terraform {
  backend "s3" {
    bucket       = "dfgjbyftd453w"
    key          = "terraform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
  }
}
