#!/bin/sh
echo ""
echo "Current working directory is $(pwd)"
echo ""

echo "Current files in $(pwd) are.."
echo "$(ls -la)"
echo ""

# Update Ubuntu
if [ -f /etc/debian_version ] || [ grep -qi ubuntu /etc/lsb-release ] || grep -qi ubuntu /etc/os-release; then
    echo "Updating Ubuntu to latest patch revision and upgrade pip install"
    echo ""
    apt-get update -y
    pip install --upgrade pip
    else
      echo 'WARN: Could not detect distro or distro unsupported'
      echo 'WARN: Trying to install ansible via pip without some dependencies'
      echo 'WARN: Not all functionality of ansible may be available'
      fi

#making sure ansible-playbook exists
echo ""
echo "Checking for ansible-playbook binary"
echo ""
if [ -e "/usr/bin/ansible-playbook" ]; then
  echo "Ansible Installation Found"
  echo ""
  else
    echo "Ansible is not installed, therefore we cannot continue."
    echo "Unable to locate ansible installation, run sandbar-install.sh to perform"
    exit 1
    fi

#making sure we can communicate using ansible to the localhost
echo "Testing ansible communication locally"
echo ""
ansible all -i "localhost," -c local -m shell -a 'df -h'
echo ""

#verify /etc/ansible/group_vars/config.yml exist
echo "Checking for existing config.yml"
echo ""
if [ -e "/etc/ansible/group_vars/config.yml" ]; then
  echo "/etc/ansible/group_vars/config.yml exist, moving on..."
  echo ""
  else
    echo "/etc/ansible/group_vars/config.yml does not exist, we cannot continue"
    echo "Obtain a copy of config.yml and adjust the variables to match your current environment and save to /etc/ansible/group_vars/. If you cannot determine those settings, you are likely best suited for a fresh install with a manual database migration"
    echo ""
    exit 1
    fi

#Cleanup if sandbar-ansible.zip exist, if so update ansible playbooks
echo "Checking if $(pwd)/sandbar-ansible.zip exist"
echo ""
if [ -e "sandbar-ansible.zip" ]; then
  echo "$(pwd)/sandbar-ansible.zip found, updating ansible playbooks"
  echo ""
  echo "Moving /etc/ansible/ansible.cfg to $(pwd)/ansible.cfg, Moving /etc/ansible/group_vars/config.yml to $(pwd)/config.yml removing /etc/ansible directory, creating /etc/ansible directory and copy $(pwd)/ansible.cfg to /etc/ansible/ansible.cfg"
  mv -f /etc/ansible/ansible.cfg . && mv -f /etc/ansible/group_vars/config.yml . && rm -rf /etc/ansible && mkdir -p /etc/ansible/group_vars && cp ansible.cfg /etc/ansible/ansible.cfg && cp config.yml /etc/ansible/group_vars/config.yml && mv ansible.cfg ansible.bak
  echo ""
  echo "Unzipping $(pwd)/sandbar-ansible.zip to /etc/ansible"
  unzip -o -q sandbar-ansible.zip -d /etc/ansible
  echo ""
elif [ -e "/etc/ansible/update.yml" ]; then
    echo "$(pwd)/sandbar-ansible.zip does not exist, but /etc/ansible/update.yml does. Therefore no updates to ansible playbooks and use the existing"
    echo ""
  else
    echo "$(pwd)/sandbar-ansible.zip not found nor does /etc/ansible/update.yml therefore we cannot continue"
    echo "Obtain a copy of sandbar-ansible.zip and ensure it's placed in $(pwd)'"
    echo ""
    exit 1
  fi

#copy sandbar application to /etc/ansible/files
echo "Preapring to copy $(pwd)/sandbar-source.zip to /etc/ansible/files"
echo ""
if [ -e "sandbar-source.zip" ]; then
  echo "Copying $(pwd)/sandbar-source.zip to /etc/ansible/files"
  mkdir -p /etc/ansible/files
  cp sandbar-source.zip /etc/ansible/files
  echo ""
  else
    echo "$(pwd)/sandbar-source.zip does not exist in current working directory $(pwd)"
    echo "Unable to update Sandbar"
    echo "Obtain a copy of sandbar-source.zip and ensure it's placed in $(pwd)'"
    exit 1
    fi

#update sandbar using ansible
echo "Preapring to update sandbar"
echo ""
if [ -e "/etc/ansible/update.yml" ]; then
  echo "Updating the sandbar application"
  echo ""
  ansible-playbook -v /etc/ansible/update.yml
  echo ""
  else
    echo "/etc/ansible/update.yml does not exist, unable to update sandbar"
    echo "Obtain a copy of sandbar-ansible because you are missing playbooks, place in $(pwd) and re-run this script"
    exit 1
    fi

