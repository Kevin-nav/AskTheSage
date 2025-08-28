
### 1. The Challenge

The initial problem was to enable two separate EC2 instances, each in a different AWS account and VPC, to communicate with each other. This was complicated by the fact that both VPCs were using the same default CIDR block, which prevents direct communication. Additionally, the goal was to allow one instance (`johnson_study_bot`) to securely access an RDS database and an S3 bucket in the other account (`adaptive-bot`).

---

### 2. The Solution: Infrastructure Setup

To solve the CIDR overlap, we created a **new VPC with a non-overlapping CIDR block (`10.0.0.0/16`)** in the `adaptive-bot`'s account. We then used a custom AMI to launch a new, identical instance (`adaptive-bot-v2`) inside this new VPC. This allowed for the following key networking configurations:

* **VPC Peering:** We established a **VPC peering connection** between the two VPCs. This created a private network link, allowing the `johnson_study_bot` to communicate with the `adaptive-bot-v2` using its private IP address. This connection is secure and does not use the public internet.
* **Route Table Updates:** We updated the route tables in both VPCs to direct traffic destined for the other VPC's CIDR block to the peering connection. This was a critical step in enabling cross-VPC communication.
* **EC2 Security Groups:** We configured the security groups on both instances to act as a firewall, allowing specific traffic (e.g., API requests) to flow between them while blocking everything else.

---

### 3. Cross-Service Communication

With the foundational networking in place, we configured the two services to work together:

#### **A. RDS Database**

To allow the `johnson_study_bot` to access the RDS database in the `adaptive-bot`'s account, we modified the **RDS security group**. The security group's inbound rules were updated to accept connections from the entire CIDR block of the `johnson_study_bot`'s VPC (`172.31.0.0/16`) on the correct port (e.g., 5432). The VPC peering connection ensures this traffic is routed securely and privately.

#### **B. S3 Bucket**

Access to the S3 bucket was handled differently, as S3 is a global service not tied to a VPC. We used **IAM (Identity and Access Management)** to grant permissions based on identity, not network location.

1.  **IAM Role and Policy:** We created a new IAM role with a custom policy (`johnson-s3-access-policy`) that granted specific permissions (`s3:GetObject`, `s3:PutObject`, `s3:ListBucket`) to a particular S3 bucket.
2.  **Attaching to the EC2 Instance:** This new role was then attached to the `johnson_study_bot` EC2 instance, giving the instance the necessary identity to access S3.
3.  **S3 Bucket Policy:** Finally, we edited the S3 bucket's policy to explicitly trust and allow access from the specific IAM role we just attached to the `johnson_study_bot`.

---

### 4. Summary

This entire setup provides a robust and secure way for your two bots to work together. We have successfully enabled:

* **Cross-Account EC2 Communication:** Through VPC peering.
* **Cross-Account RDS Access:** Through a security group and VPC peering.
* **Cross-Account S3 Access:** Through IAM roles and policies.

The old `adaptive-bot` instance was successfully replaced by the `adaptive-bot-v2` instance in the correct VPC, ensuring a clean and cost-effective architecture.