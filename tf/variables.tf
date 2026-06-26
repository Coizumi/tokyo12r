variable "tenancy_ocid" {
  type        = string
  description = "OCI tenancy OCID."
}

variable "user_ocid" {
  type        = string
  description = "OCI API user OCID."
}

variable "compartment_ocid" {
  type        = string
  description = "Compartment OCID where TOKYO12R resources are created."
  default     = "ocid1.compartment.oc1..aaaaaaaaavsn2rim6u3ka66526ggdbkd2gvxi26woaz2oau7gugvkep6vg4a"
}

variable "fingerprint" {
  type        = string
  description = "OCI API key fingerprint."
}

variable "private_key_path" {
  type        = string
  description = "Local path to the OCI API private key PEM."
}

variable "region" {
  type        = string
  description = "OCI region identifier."
  default     = "ap-tokyo-1"
}

variable "project_name" {
  type        = string
  description = "Project name used for display names and tags."
  default     = "tokyo12r"
}

variable "admin_cidr" {
  type        = string
  description = "CIDR allowed to SSH into the instance, for example 203.0.113.10/32."
  nullable    = true

  validation {
    condition     = var.admin_cidr == null || can(cidrhost(var.admin_cidr, 0))
    error_message = "admin_cidr must be null or a valid CIDR block such as 203.0.113.10/32."
  }
}

variable "vcn_cidr" {
  type        = string
  description = "VCN CIDR block."
  default     = "10.12.0.0/16"
}

variable "public_subnet_cidr" {
  type        = string
  description = "Public subnet CIDR block."
  default     = "10.12.1.0/24"
}

variable "ssh_public_key_path" {
  type        = string
  description = "Local path to the SSH public key injected into the compute instance."
}

variable "instance_shape" {
  type        = string
  description = "OCI compute shape."
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  type        = number
  description = "OCPUs for the flexible shape."
  default     = 1
}

variable "instance_memory_gbs" {
  type        = number
  description = "Memory in GiB for the flexible shape."
  default     = 6
}

variable "boot_volume_size_in_gbs" {
  type        = number
  description = "Boot volume size in GiB."
  default     = 50
}

variable "availability_domain" {
  type        = string
  description = "Optional availability domain name. Defaults to the first AD in the tenancy."
  default     = null
}

variable "image_ocid" {
  type        = string
  description = "Optional explicit OS image OCID. When null, Terraform selects the latest matching image."
  default     = null
}

variable "image_operating_system" {
  type        = string
  description = "Operating system filter used when image_ocid is null."
  default     = "Oracle Linux"
}

variable "image_operating_system_version" {
  type        = string
  description = "Operating system version filter used when image_ocid is null."
  default     = "9"
}

variable "ssh_user" {
  type        = string
  description = "Default SSH user for the selected image."
  default     = "opc"
}
