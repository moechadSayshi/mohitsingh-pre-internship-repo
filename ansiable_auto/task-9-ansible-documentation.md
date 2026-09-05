# Task 9: Automate Twenty CRM with Ansible

## Overview

For Task 9, I automated the deployment of Twenty CRM using Ansible inside a Linux playground environment.

The automation was tested against two Ubuntu worker nodes:

- `worker_node_1`
- `worker_node_2`

The goal was to make the setup repeatable, configurable, verifiable, and idempotent.

## Architecture

```text
                         Ansible Control Node
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
             worker_node_1               worker_node_2
                    |                           |
              Docker Engine                Docker Engine
                    |                           |
                    v                           v
             Twenty CRM                  Twenty CRM
              :2020                         :2020
```

Ansible applies the same desired configuration to both worker nodes.

## Project Structure

```text
task-9/
├── inventory.ini
├── site.yml
├── group_vars/
│   └── all.yml
└── templates/
    └── docker-compose.yml.j2
```

| File                              | Purpose                                                       |
| --------------------------------- | ------------------------------------------------------------- |
| `inventory.ini`                   | Defines the target worker nodes and SSH settings              |
| `site.yml`                        | Main Ansible playbook containing the automation               |
| `group_vars/all.yml`              | Centralized application variables                             |
| `templates/docker-compose.yml.j2` | Jinja2 template used to generate Docker Compose configuration |

## 1. Ansible Inventory

The inventory contains both worker nodes:

```ini
[servers]

worker_node_1 ansible_host=YOUR_IP_ADDRESS ansible_user=ubuntu
worker_node_2 ansible_host=YOUR_IP_ADDRESS ansible_user=ubuntu

[all:vars]

ansible_ssh_private_key_file=/home/ubuntu/ssh-master-key
ansible_python_interpreter=/usr/bin/python3
host_key_checking=false
```

### Connectivity verification

```bash
ansible -i inventory.ini servers -m ping
```

Both hosts successfully returned:

```text
"ping": "pong"
```

This confirmed that the inventory and SSH configuration were working correctly.

## 2. Configuration Variables

`group_vars/all.yml`:

```yaml
app_user: twenty
app_dir: /opt/twenty

twenty_repo: "https://github.com/PearlThoughts-Intern-DevOps/devops-crm-project.git"
twenty_branch: main

twenty_port: 2020
```

Using variables keeps application configuration separate from the main automation logic and makes the deployment reusable.

## 3. Installing Required Dependencies

The playbook installs:

- Git
- curl
- Python 3
- Python 3 pip
- ca-certificates
- gnupg

The installation is performed using Ansible's `apt` module.

## 4. Installing Docker

The worker nodes initially did not have an available package named `docker` through their configured repositories.

The playbook therefore:

1. Creates `/etc/apt/keyrings`.
2. Downloads Docker's GPG key.
3. Adds Docker's official Ubuntu repository with `deb822_repository`.
4. Installs:
   - Docker Engine
   - Docker CLI
   - containerd
   - Docker Buildx
   - Docker Compose plugin
5. Starts and enables Docker.

This makes Docker installation repeatable on both worker nodes.

## 5. Dedicated Application User

A dedicated application user named `twenty` was created.

```yaml
- name: Create application user
  ansible.builtin.user:
    name: "{{ app_user }}"
    shell: /bin/bash
    create_home: true
    state: present

- name: Add application user to Docker group
  ansible.builtin.user:
    name: "{{ app_user }}"
    groups:
      - docker
    append: true
```

The user separates application ownership from the default SSH user.

## 6. Application Directories

The playbook creates:

```text
/opt/twenty
/opt/twenty/compose
```

with `twenty:twenty` ownership and mode `0755`.

## 7. Cloning the Twenty CRM Repository

The repository is maintained at:

```text
/opt/twenty/repo
```

The playbook uses Ansible's Git module:

```yaml
- name: Clone Twenty CRM repository
  ansible.builtin.git:
    repo: "{{ twenty_repo }}"
    dest: "{{ app_dir }}/repo"
    version: "{{ twenty_branch }}"
    update: true
    force: false
```

### Git safe-directory issue

During a second playbook execution, Git reported:

```text
detected dubious ownership in repository at '/opt/twenty/repo'
```

This occurred because the repository ownership had been assigned to the dedicated `twenty` user while the Git task was executed with elevated privileges.

The playbook was updated to check for the `.git` directory and mark the repository as safe:

```yaml
- name: Check whether Twenty CRM repository exists
  ansible.builtin.stat:
    path: "{{ app_dir }}/repo/.git"
  register: twenty_git_repo

- name: Mark Twenty CRM repository as a safe Git directory
  ansible.builtin.command:
    cmd: "git config --system --add safe.directory {{ app_dir }}/repo"
  when: twenty_git_repo.stat.exists
  changed_when: false
```

Repository ownership is then explicitly set to `twenty:twenty`.

## 8. Jinja2 Docker Compose Template

The Docker Compose configuration is stored as:

```text
templates/docker-compose.yml.j2
```

The template uses variables such as:

```yaml
ports:
  - "{{ twenty_port }}:2020"
```

and:

```yaml
SERVER_URL: "http://localhost:{{ twenty_port }}"
```

Ansible renders the template into the target host's Compose configuration.

## 9. Twenty CRM Docker Compose Configuration

The generated Compose configuration uses the Twenty development image:

```yaml
services:
  twenty:
    image: twentycrm/twenty-app-dev:latest
    container_name: twenty-app-dev
    restart: unless-stopped

    ports:
      - "{{ twenty_port }}:2020"

    environment:
      NODE_PORT: 2020
      SERVER_URL: "http://localhost:{{ twenty_port }}"

    volumes:
      - twenty_data:/app/.local-storage

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:2020/healthz"]
      interval: 10s
      timeout: 5s
      retries: 60
      start_period: 180s

volumes:
  twenty_data:
```

This provides the Twenty CRM container, port mapping, persistent storage, restart policy, and health check.

## 10. Ansible Handler

A handler restarts/recreates Twenty CRM when the Compose configuration changes:

```yaml
handlers:
  - name: Restart Twenty CRM
    community.docker.docker_compose_v2:
      project_src: "{{ app_dir }}/compose"
      state: present
      recreate: always
    become: true
```

The template task notifies the handler only when the rendered configuration changes.

## 11. Starting Twenty CRM

The deployment uses the `community.docker` collection and Docker Compose v2:

```yaml
- name: Start Twenty CRM
  community.docker.docker_compose_v2:
    project_src: "{{ app_dir }}/compose"
    state: present
  become: true
```

## 12. Application Health Check

The playbook waits for:

```text
http://127.0.0.1:2020/healthz
```

using:

```yaml
- name: Wait for Twenty CRM health endpoint
  ansible.builtin.uri:
    url: "http://127.0.0.1:{{ twenty_port }}/healthz"
    method: GET
    status_code: 200
  register: health
  retries: 36
  delay: 10
  until: health.status == 200
```

This ensures Ansible does not report deployment success until the application is responding.

## 13. Container Verification

The playbook verifies the container:

```yaml
- name: Check Twenty CRM container
  ansible.builtin.command:
    cmd: docker ps --filter name=twenty-app-dev --format "{{ '{{' }}.Status{{ '}}' }}"
  register: container_status
  changed_when: false
```

It then checks that the returned status is non-empty with an assertion.

## 14. Deployment Verification

The containers were verified with:

```bash
ansible servers -i inventory.ini -m shell   -a "sudo docker ps --filter name=twenty-app-dev"
```

Both worker nodes showed the `twenty-app-dev` container.

The application health endpoint was verified with:

```bash
ansible servers -i inventory.ini -m shell   -a "sudo curl -s http://localhost:2020/healthz"
```

This confirmed that Twenty CRM was responding successfully on both nodes.

## 15. Troubleshooting Performed

### Docker package unavailable

The initial task using:

```yaml
ansible.builtin.package:
  name: docker
  state: present
```

failed with:

```text
No package matching 'docker' is available
```

**Resolution:** Added Docker's official repository and installed the Docker Engine and Compose packages from it.

### Deprecated repository module

The initial Docker repository task used:

```text
ansible.builtin.apt_repository
```

The installed Ansible version reported that this module was deprecated.

**Resolution:** Replaced it with:

```text
ansible.builtin.deb822_repository
```

### Unprivileged `become_user` problem

Running the Git task as an unprivileged `twenty` user caused Ansible to fail while setting permissions on temporary module files.

**Resolution:** Removed the problematic `become_user` usage, used elevated execution for the Git task, and managed repository ownership explicitly.

### Git dubious ownership

A later playbook run failed because Git detected that `/opt/twenty/repo` was owned by another user.

**Resolution:** Added explicit Git safe-directory handling.

### Docker socket permission

An ad-hoc command executed without `sudo` returned:

```text
permission denied while trying to connect to the Docker API at unix:///var/run/docker.sock
```

Using `sudo docker ps` allowed the verification command to run successfully.

This also demonstrated that adding a user to the Docker group does not automatically refresh already-established SSH sessions.

## 16. Idempotency

Idempotency was tested by running:

```bash
ansible-playbook -i inventory.ini site.yml
```

more than once.

The subsequent execution completed successfully without unnecessarily rebuilding the entire environment.

The playbook is designed around the desired state:

- Existing packages are not unnecessarily reinstalled.
- Existing users remain unchanged.
- Existing directories remain unchanged.
- The Git repository is maintained rather than recloned unnecessarily.
- The Compose configuration is only acted on when it changes.
- The application is not unnecessarily restarted when the template has not changed.

## 17. Final Verification Commands

### Connectivity

```bash
ansible servers -i inventory.ini -m ping
```

### Deployment

```bash
ansible-playbook -i inventory.ini site.yml
```

### Container verification

```bash
ansible servers -i inventory.ini -m shell   -a "sudo docker ps --filter name=twenty-app-dev"
```

### Health verification

```bash
ansible servers -i inventory.ini -m shell   -a "sudo curl -s http://localhost:2020/healthz"
```

### Idempotency verification

```bash
ansible-playbook -i inventory.ini site.yml
```

## 18. Result

Twenty CRM was successfully automated and deployed on both worker nodes:

```text
worker_node_1
    └── Docker
        └── Twenty CRM
            └── :2020
                └── /healthz → successful

worker_node_2
    └── Docker
        └── Twenty CRM
            └── :2020
                └── /healthz → successful
```

The implementation covers the required Task 9 areas:

- Inventory with target hosts
- Dependency installation
- Docker installation
- Dedicated application user
- Application directories and permissions
- Twenty CRM repository cloning
- Ansible variables
- Jinja2 configuration template
- Docker Compose deployment
- Ansible handler for configuration changes
- Application health verification
- Repeatable/idempotent execution

## 19. What I Learned

This task gave me practical experience with:

- Ansible inventory management
- Playbooks and tasks
- Privilege escalation
- Ansible variables
- Jinja2 templates
- Handlers
- Docker and Docker Compose automation
- Git automation
- Health checks
- Troubleshooting remote deployments
- Idempotent infrastructure configuration

The main lesson was that infrastructure automation needs to account for permissions, package repositories, ownership, service readiness, and repeated execution, not just the initial deployment.
