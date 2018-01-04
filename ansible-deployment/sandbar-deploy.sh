#!/bin/sh

echo ""
echo "Current working directory is $(pwd)"
echo ""

echo "Current files in $(pwd) are.."
echo "$(ls -la)"
echo ""

if [ -f /etc/debian_version ] || [ grep -qi ubuntu /etc/lsb-release ] || [ grep -qi ubuntu /etc/os-release ];
then
  # Install via package
  echo "Updating Ubuntu to latest patch revision, adding Ansible repository and installing Ansible"
  echo ""
  apt-get update -y && \
  apt-get install --no-install-recommends -y software-properties-common -y && \
  apt-add-repository ppa:ansible/ansible -y && \
  apt-get update -y && \
  apt-get install -y ansible

  # Install required Python libs and Python package managemnet system PIP
  echo "Installing required Python librairies and Python package managemnet system PIP"
  echo ""
  apt-get install -y  python-pip python-yaml python-jinja2 python-httplib2 python-paramiko python-pkg-resources
  [ -n "$( apt-cache search python-keyczar )" ] && apt-get install -y  python-keyczar
  pip install --upgrade pip
  if [ ! apt-get install -y git ];
  then
    apt-get install -y git-core
    pip install --upgrade pip
  fi

  # If python-pip install failed and setuptools exists, try this
  if [ -z "$(which pip)" -a -z "$(which easy_install)" ];
  then
    echo "python-pip failed to install, attempting an an alternative install method"
    echo ""
    apt-get -y install python-setuptools
    easy_install pip
    pip install --upgrade pip
  elif [ -z "$(which pip)" -a -n "$(which easy_install)" ];
  then
    easy_install pip
    pip install --upgrade pip
  else
    echo "pip install failed"
  fi

  # If python-keyczar apt package does not exist, use pip
  [ -z "$( apt-cache search python-keyczar )" ] && sudo pip install python-keyczar

  # Install passlib for encrypt
  apt-get install -y build-essential
  apt-get install -y python-all-dev python-mysqldb sshpass && pip install pyrax pysphere boto passlib dnspython

  # Install Ansible module dependencies
  apt-get install -y bzip2 file findutils git gzip mercurial procps subversion sudo tar debianutils unzip xz-utils zip python-selinux python-apt

  # Create inventory file for localhost
  echo "[local]\nlocalhost ansible_connection=local\n" > /etc/ansible/hosts
  echo ""
else
  echo 'WARN: Could not detect distro or distro unsupported'
  echo 'WARN: Trying to install ansible via pip without some dependencies'
  echo 'WARN: Not all functionality of ansible may be available'
fi

#making sure ansible-playbook exists
echo "Checking for ansible-playbook binary"
echo ""

if [ -e "/usr/bin/ansible-playbook" ];
then
  echo "Ansible Installation Found"
  echo ""
else
  echo "Ansible is not installed, there we cannot continue."
  echo "Please review the log /var/log/sandbar-deploy.log for installation errors"
  exit 1
fi

#making sure we can communicate using ansible to the localhost
echo "Testing ansible communication locally"
echo ""
ansible all -i "localhost," -c local -m shell -a 'df -h'
echo ""

#enabling ansible logging
echo "Preparing to enable ansible logging"
echo ""
if [ -e "/etc/ansible/ansible.cfg" ];
then
  echo "Enabling ansible logging"
  sed -i 's/^#log_path/log_path/' /etc/ansible/ansible.cfg
  echo ""
else
  echo "/etc/ansible/ansible.cfg does not exists, cannot continue."
  echo "The ansible.cfg file is missing which is likely due to an incomplete install of Ansible, review /var/log/sandbar-deploy.log"
  exit 1
fi

#Cleanup ansible directory, if exist
echo "Checking for existing ansible playbooks"
echo ""
if [ -e "/etc/ansible/*.yml" ];
then
  echo "Moving /etc/ansible/ansible.cfg to $(pwd)/ansible.cfg, removing /etc/ansible directory, creating /etc/ansible directory and copy $(pwd)/ansible.cfg to /etc/ansible/ansible.cfg"
  mv /etc/ansible/ansible.cfg . && rm -rf /etc/ansible && mkdir -p /etc/ansible/group_vars && cp ansible.cfg /etc/ansible/ansible.cfg && mv ansible.cfg ansible.bak
  echo ""
else
  echo "Existing ansible playbooks not found, this is informational"
  echo ""
fi

#Ensure /etc/ansible/group_vars exist
echo "Checking if /etc/ansible/group_vars exist, otherwise create"
echo ""
if [ -e "/etc/ansible/group_vars" ];
then
  echo "/etc/ansible/group_vars already exist, this is informational"
  echo ""
else
  echo "/etc/ansible/group_vars does not exist, creating now..."
  mkdir -p /etc/ansible/group_vars
  echo ""
fi

#copying config.yml to /etc/ansible/group_vars
echo "Preapring to copy $(pwd)/config.yml to /etc/ansible/group_vars"
echo ""
if [ -e "config.yml" ];
then
  echo "Copying config.yml from $(pwd) to /etc/ansible/group_vars"
  cp config.yml /etc/ansible/group_vars/config.yml
  echo ""
else
  echo "config.yml does not exist in current working directory $(pwd)"
  echo "Please ensure config.yml exist in $(pwd)"
  echo ""
  exit 1
fi

#copy ansible playbooks to /etc/ansible
echo "Preapring to unzip $(pwd)/sandbar-ansible.zip to /etc/ansible"
echo ""
if [ -e "sandbar-ansible.zip" ];
then
  echo "Unzipping $(pwd)/sandbar-ansible.zip to /etc/ansible"
  unzip -o -q sandbar-ansible.zip -d /etc/ansible
  echo ""
else
  echo "$(pwd)/sandbar-ansible.zip does not exist in current working directory $(pwd)"
  echo "Please ensure sandbar-ansible.zip exist in $(pwd)"
  echo ""
  exit 1
fi

#copy sandbar application to /etc/ansible/files
echo "Preapring to copy $(pwd)/sandbar-source.zip to /etc/ansible/files"
echo ""
if [ -e "sandbar-source.zip" ];
then
  echo "Copying $(pwd)/sandbar-source.zip to /etc/ansible/files"
  mkdir -p /etc/ansible/files
  cp sandbar-source.zip /etc/ansible/files
  echo ""
else
  echo "$(pwd)/sandbar-source.zip does not exist in current working directory $(pwd)"
  echo "Please ensure sandbar-source.zip exist in $(pwd)"
  echo ""
  exit 1
fi

#deploy sandbar using ansible
echo "Preapring to deploy sandbar"
echo ""
if [ -e "/etc/ansible/deploy.yml" ];
then
  echo "deploying sandbar application"
  echo ""
  ansible-playbook -v /etc/ansible/deploy.yml
  echo ""
else
  echo "/etc/ansible/deploy.yml does not exist, unable to deploy sandbar"
  echo "The ansible playbooks do not exist, please re-run this script. If failure continues, please review /var/log/deploy-sandbar.log"
  exit 1
fi