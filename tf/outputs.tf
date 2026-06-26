output "instance_public_ip" {
  description = "Public IP address of the pipeline instance."
  value       = oci_core_instance.pipeline.public_ip
}

output "ssh_command" {
  description = "SSH command for the selected image default user."
  value       = "ssh -i ${replace(var.ssh_public_key_path, ".pub", "")} ${var.ssh_user}@${oci_core_instance.pipeline.public_ip}"
}

output "selected_image_id" {
  description = "Image OCID selected for the compute instance."
  value       = local.selected_image_id
}
