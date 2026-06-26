locals {
  tags = {
    project = var.project_name
    role    = "feature-pipeline"
  }

  is_flexible_shape = endswith(var.instance_shape, ".Flex")

  availability_domain = coalesce(
    var.availability_domain,
    data.oci_identity_availability_domains.this.availability_domains[0].name
  )

  selected_image_id = coalesce(
    var.image_ocid,
    data.oci_core_images.compute.images[0].id
  )
}

data "oci_identity_availability_domains" "this" {
  compartment_id = var.tenancy_ocid
}

data "oci_core_images" "compute" {
  compartment_id           = var.tenancy_ocid
  operating_system         = var.image_operating_system
  operating_system_version = var.image_operating_system_version
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "tokyo12r-vcn"
  dns_label      = "tokyo12r"
  freeform_tags  = local.tags
}

resource "oci_core_internet_gateway" "this" {
  compartment_id = var.compartment_ocid
  display_name   = "tokyo12r-igw"
  enabled        = true
  vcn_id         = oci_core_vcn.this.id
  freeform_tags  = local.tags
}

resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  display_name   = "tokyo12r-public-rt"
  vcn_id         = oci_core_vcn.this.id
  freeform_tags  = local.tags

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.this.id
  }
}

resource "oci_core_subnet" "public" {
  cidr_block                 = var.public_subnet_cidr
  compartment_id             = var.compartment_ocid
  display_name               = "tokyo12r-public-subnet"
  dns_label                  = "public"
  prohibit_public_ip_on_vnic = false
  route_table_id             = oci_core_route_table.public.id
  vcn_id                     = oci_core_vcn.this.id
  freeform_tags              = local.tags
}

resource "oci_core_network_security_group" "pipeline" {
  compartment_id = var.compartment_ocid
  display_name   = "tokyo12r-pipeline-nsg"
  vcn_id         = oci_core_vcn.this.id
  freeform_tags  = local.tags
}

resource "oci_core_network_security_group_security_rule" "ssh" {
  count = var.admin_cidr == null ? 0 : 1

  network_security_group_id = oci_core_network_security_group.pipeline.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = var.admin_cidr
  source_type               = "CIDR_BLOCK"
  description               = "SSH from administrator CIDR"

  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}

resource "oci_core_network_security_group_security_rule" "egress_all" {
  network_security_group_id = oci_core_network_security_group.pipeline.id
  direction                 = "EGRESS"
  protocol                  = "all"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  description               = "Outbound internet access for JRA, GitHub, and package updates"
}

resource "oci_core_instance" "pipeline" {
  availability_domain = local.availability_domain
  compartment_id      = var.compartment_ocid
  display_name        = "tokyo12r-pipeline"
  shape               = var.instance_shape
  freeform_tags       = local.tags

  dynamic "shape_config" {
    for_each = local.is_flexible_shape ? [1] : []

    content {
      ocpus         = var.instance_ocpus
      memory_in_gbs = var.instance_memory_gbs
    }
  }

  create_vnic_details {
    assign_public_ip = true
    display_name     = "tokyo12r-pipeline-vnic"
    hostname_label   = "pipeline"
    nsg_ids          = [oci_core_network_security_group.pipeline.id]
    subnet_id        = oci_core_subnet.public.id
  }

  metadata = {
    ssh_authorized_keys = file(var.ssh_public_key_path)
    user_data           = base64encode(file("${path.module}/cloud-init.yaml"))
  }

  source_details {
    source_id               = local.selected_image_id
    source_type             = "image"
    boot_volume_size_in_gbs = var.boot_volume_size_in_gbs
  }
}
