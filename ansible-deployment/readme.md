# Deployment, Installation, and Updating

## Setting up

Sandbar uses a fully-automated set of scripts and Ansible playbooks to install itself, and this is the recommended method of installation and update for Sandbar instances. To install Sandbar using this method, all you need is:

* A Ubuntu 16.04 LTS server
* A sudo-empowered account
* SSH or Shell access

Upload the provided `Sandbar.zip` file to the server into your user account's home directory (home is recommended, not required).

The file `config.yml` in the working directory is where things like usernames, passwords, and installation directories are set. For security reasons, it is recommended that the passwords be changed, but usernames and other variables may be left as is. The file itself contains numerous line-by-line instructions on what needs to be changed and why. Review the file, make the necessary changes, and save it.

Before you install, you will need to make sure that the hostname of the destination server is set. The result of `hostname -f` should return the fully qualified domain name that you intend to direct public web traffic to. This can be done on Ubuntu 16.04+ with the following command:

> `hostnamectl set-hostname new-hostname`

You will also then need to edit `/etc/hosts` as follows:

> `127.0.1.1     your-old-hostname`

If you don't set up the hostname before installing, after installing you will need to modify the variables:

1. The value of `server_name` in `/etc/nginx/conf.d/{{project.name}}.conf`, the line and restart nginx `sudo systemctl restart nginx`
2. This line `HOST = 'http://{{ansible_fqdn}}'` in `./ansible-deployment/sandbar-ansible/roles/django/templates/settings.py`

## Installing

Assuming that the `sandbar.zip` file is present in your home folder, that the hostname of the server is set correct, and that `config.yml` has been modified with the desired values, all that needs to be done to install sandbar is to run the following command in your home folder.

> `sudo apt-get install unzip && unzip ./sandbar.zip -d ~/sandbar && cd ~/sandbar && sudo sh ./sandbar-deploy.sh 2>&1 | sudo tee -a /var/log/sandbar-deploy.log`

This unzips the `Sandbar.zip` containing Sandbar's source code, deployment and update scripts, and Ansible playbooks into a "working" directory called `sandbar` in the current user's home directory, and then runs the deployment script.

In most cases, you're done! Your new Sandbar instance will be accessible at the hostname you specified, but keep in mind that the anti-analysis will prevent access everywhere but at a valid application URL like `/engagements/list`.

### Advanced usage

Advanced users may modify the above command to unzip the sandbar source files anywhere they please.

Note that the installation and update scripts for Sandbar are located in this working directory by default, so you must be *in* that directory to run them later or you must specify their full path. This guide assumes you will have used `~/sandbar` as your working directory.

## Updating Sandbar

When an update to the application is ready, you will be provided with an updated copy of `sandbar-source.zip` if Sandbar needs to be updated. You may also be provided with an updated copy of `sandbar-ansible.zip` if changes have been made to our deployment and updating scripts. On rare occasions, new versions of the scripts (like `sandbar-deploy.sh` may be provided as well). Simply copy all new files into your sandbar installation directory (this tutorial assumes `~/sandbar/`) directory and overwrite the existing ones.

Note that overwriting the old files with the new ones will not affect your existing Sandbar installation's data in any way, as these zip files contain only *source code* of the application and deployment solution.

To actually apply the updates, you must run the following command:

> `sudo sh ./sandbar-update.sh 2>&1 | sudo tee -a /var/log/sandbar-update.log`