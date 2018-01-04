# Project Sandbar

Sandbar is Rhino Security Labs' proprietary platform for conducting social engineering / phishing engagements.

## Architectural Overview - Stack

* Runs on Django with Python 2.7 in a virtual enviroment
* Uses Postgres SQL as a backend
* NGINX is used as the HTTP host
* UWSGI provides the interface between NGINX (static host) and Django (python application)
* Sandbar uses Celeryd/Celerybeat for task scheduling and execution
* RabbitMQ provides asynchronus messaging between Django and Celery

## Architectural overview - Operational

* Sandbar requires at least one set of SMTP credentials to send phishing emails, though any number of email accounts may be configured within Sandbar
* Sandbar supports dynamic hostname proxies for use as "Landing Pages." This will require altering the DNS records of domains to be used for phishing.

## Architectural overview - Django Dependencies

* amqp==1.4.9
* anyjson==0.3.3
* beautifulsoup4==4.4.1
* billiard==3.3.0.21
* celery==3.1.19
* Django==1.8.6
* django-bootstrap3==6.2.2
* django-celery==3.1.17
* django-ckeditor==5.0.2
* django-registration==2.0.3
* kombu==3.0.33
* lxml==3.5.0
* psycopg2==2.6.1
* pycrypto==2.6.1
* pytz==2015.7
* uWSGI==2.0.11.2
* wheel==0.24.0

## Capabilities (current)

* Local replication of target web pages for use as "landing" pages
* Collection of information entered into landing page forms
* Rich-text (i.e. HTML) email creation via WYSIWYG editor
* Allow creation of targets from CSV files (email, firstname, lastname)
* Allow scheduled sending of N-size batches of emails to targets
* Track email opens, link clicks, landing-page hits, and landing-page-form-submits, per target
* Admin UI to for CRUD and viewing of application data and state
* Support multiple landing pages with their own TLDs.
* Allow the import and parsing of any number of additional columns in CSV, for use in creating groups of targets
* Implement support for collection of addition target data fields (e.g. Middle name, mother's name, etc)
* Add support for dynamic short-codes for use in emails, drawing data from additional target fields
* Add Email History and Queue view, which will allow Rhino to see who/when was PREVIOUSLY sent emails, as well as FUTURE emails in the queue (w/ associated times)


## Capabilities (future)

* Implement XML report exporting for use in Javan
* Eliminate Cookies from Target-side views (ticket #211)
* Refactor: split Landing Page and Redirect page into separate models + methods (ticket #272)
* Admin Settings in Sandbar/Settings submenu (ticket #269)
* In-App notification system (ticket #257)
* Replace JS alerts with custom modals (ticket #253)
* Allow "shutdown" of engagements (ticket #250)
* Scraped and Manual redirect pages still use `/save-response/` in their URL (ticket #247)
* Django + 1.9 require + postgres 9.4 (ticket #237)
* Do not allow completed engagements to be restarted (ticket #241)
* Add "Reschedule" button for Engagements + related changes (ticket #239)
* Add "Rebuild" button for Engagements + related changes (ticket #240)
* Decouple "Target List" and "Vector Email" orderings and contents (ticket #238)
* Add "Duplicate" Engagement button (ticket #242)
* [WIP] Allow editing of status for individual Vector Emails (ticket #204)
* Bring "Extend/Add-to" Target lists up to date (ticket #234)
* Implement "Author" t racking, Allow Filtering preferences for list views (ticket #225)
* Change referral ID to connect to VectorEmails instead of Targets (ticket #212)
* Cookie Encryption (Fix after SSL is implemented) (ticket #209)
* Proof-of-Concept Items for Sandbar (The Future is Now!) (ticket #199)
* Sandbar as a Software as a Service (SSASS) (BETA) (ticket #198)
* Sandbar Roadmap (ticket #197)
* Crawler-proof site (ticket #196)
* Add "reverse" reporting for Assessments (ticket #183)
* Control access to Landing Pages (ticket #176)
* Fix to Unknown/Deleted Engagement Events (ticket #163)

* Warning if any users in a CSV have a different email domain or follow different naming syntax
* Allow a single user's phishing script to be edited on a one-off basis without changing the template email in the associated target group
* Successes grouped by emails/websites/other groupings (dept? custom groupings?)
* Combine multiple SE Campaigns into one report?  (lower priority)
* Track emails (bounces/successful receipts)

* Integrate information gathering (domain searching, user email enumeration, etc) plugins
* 2FA and Additional Authentication Controls* Auth0?
* Namecheap API integration for In-App domain search, purchase, and nameserver config
* Namecheap API integration for SMTP creation and configuration

# General Development Procedures

Rhino administration will usually issue development requests in the form of a Bitbucket issue in the [issue tracker][].

[issue tracker]: https://bitbucket.org/xander-sereda/sandbar/issues?status=new&status=open

Try to make one commit per major feature, but you can bundle lots of little features. Use common sense. Please include the tracker-assigned issue number in the commit message like so:

`git commit -m "#34 and #67 - fixed formatting issues on the widget"`

This is so that testers and Rhino personnel can figure out what was fixed when and by who from the commit history. Updating the actual live server requires an actual merge into Master.

## Acceptance Testing

When you have completed a feature, you should go into the related issue(s) in the tracker, and assign the issue back to the designated PM / QA tester so that the change can be reviewed and approved.

## Git Branches and Flows

Developers should be aware of the branch structure shown below. Dev should generally be used as a base for feature branches, and NOT master. Similarly, when a feature branch is completed, it should be merged back into Dev. Developers can merge code into the Dev branch on their own, without prior permission.

Developers should NOT merge changes from their feature branches directly into Master, nor should they merge Dev into Master. The Dev branch will be periodically be merged into Master by Rhino management.

    Master__ _________________________ ________ ... updated Master continues
            |                         |
            |__ Dev __ _______________|_________ ___ _____ ... Dev continues
                      |                         |   |
                      |__ Feature Branch #1 ____|   |
                      |                             |
                      |__ Feature Branch #2 ________|

# Deployment, Installation, and Updating

## General

See `./ansible-deployment/readme.md` for a user-friendly walkthrough of the installation process. This section will only list the commands and notes for developers.

Quick stop / start / restart commands for the stack:

* `sudo systemctl reload-or-restart uwsgi-sandbar && sudo systemctl reload-or-restart nginx.service && sudo systemctl reload-or-restart celeryd.service && sudo systemctl reload-or-restart celerybeat.service && sudo systemctl reload-or-restart rabbitmq-server.service`
* `sudo systemctl stop uwsgi-sandbar && sudo systemctl stop nginx.service && sudo systemctl stop celeryd.service && sudo systemctl stop celerybeat.service && sudo systemctl stop rabbitmq-server.service`
* `sudo systemctl start uwsgi-sandbar && sudo systemctl start nginx.service && sudo systemctl start celeryd.service && sudo systemctl start celerybeat.service && sudo systemctl start rabbitmq-server.service`

If you get strange errors or errors relating to bash scripts, python files, or anything that might be sensitive to the Windows-style line endings, use the following command to replace all invalid line endings in file or directory causing the problem:

> `dos2unix ~/sandbar/*`

or

> `dos2unix sandbar-deploy.sh`

Deployment logs are stored as:
    * /var/log/sandbar-deploy.log
    * /var/log/ansible.log

Django's operational logs are stored in `/opt/sandbar/debug.log`.

## Quick-install

### Prep

Before you install, you will need to make sure that the hostname of the destination server is set. The result of `hostname -f` should return the fully qualified domain name that you intend to direct public web traffic to. This can be done on Ubuntu 16.04+ with the following command:

> `hostnamectl set-hostname new-hostname`

You will also then need to edit `/etc/hosts` as follows:

> `127.0.1.1     your-old-hostname`

If you don't set up the hostname before installing, after installing you will need to modify the variables:

1. The value of `server_name` in `/etc/nginx/conf.d/{{project.name}}.conf`, the line and restart nginx `sudo systemctl restart nginx`
2. This line `HOST = 'http://{{ansible_fqdn}}'` in `./ansible-deployment/sandbar-ansible/roles/django/templates/settings.py`

### Install

This is the one-liner for unpacking and installing a pre-exsting `sandbar.zip` file. If you need to adjust configuration details or create a new `sandbar.zip`, see below.

> `sudo apt-get install unzip && unzip ./sandbar.zip -d ~/sandbar && cd ~/sandbar && sudo sh ./sandbar-deploy.sh 2>&1 | sudo tee -a /var/log/sandbar-deploy.log`

Breaking that into steps, we have:

1. `sudo apt-get install unzip` - install the utility to open zip files.
2. `unzip ./sandbar.zip -d ~/sandbar` - unzip the `sandbar.zip` into a folder called `sandbar`, which is created in the current working directory.
3. `cd ~/sandbar` - move into the new `sandbar` folder.
4. `sudo sh ./sandbar-deploy.sh 2>&1 | sudo tee -a /var/log/sandbar-deploy.log` - runs the deploy script and copy the output to a log file for later reference.

## Detailed Installation & Preparation of new `sandbar.zip` files

### Prep

The contents of `sandbar.zip` should look like below. Pay special attention to the fact that the zip files inside do NOT contain directories of the same name - just the files themselves.

* sandbar-ansible.zip <-- Ansible Playbooks, NOT in a directory
    * files/ <-- Empty
    * group_vars/
        * package-versions.yml <-- Specifies versions of core packages that updates don't break Sandbar
    * roles/ < Contains configs and playbooks for all Ansible tasks (Django installation, for example)
        * ...
        * django
            * tasks
                * ...
            * templates
                * settings.py <-- Important! This is settings.py that is used for Django-specific configuration details.
        * ...
    * deploy.yml <-- Ansible-specific playbook
    * hosts <-- Not necessary to modify this since installation is local
    * restart-services.yml <-- Playbook for restarting core Sandbar services
    * update.yml <-- Playbook for updating the sandbar source code
* sandbar-source.zip <-- Sandbar application
    * client/
    * page_parser
    * requirements/
    * sandbar/
    * static/
    * templates/
    * test_data/
    * utilities/
    * .coveragerc
    * manage.py
* sandbar-deploy.sh <-- Deployment script
* sandbar-update.sh <-- Update script
* config.yml <-- Passwords, usernames and other Variables go in here
* readme.md

When you're assembling a new `sandbar.zip`, usually what you'll want to do first is modify the `config.yml` file to reflect the passwords and usernames you'll want on the target server.

The next thing you'll usually do is package up the latest build of sandbar. To do this, use `git` to get the latest code and zip up everyting inside the repo *except* the `ansible-deployment` folder. The resulting zip file should be called `sandbar-source.zip` and its structure is as shown above. Move `sandbar-source.zip` into the `ansible-deployment` folder.

Next, you will want to move inside the `ansible-deployment/sandbar-ansible` folder and zip the **contents** into a zip file called `sandbar-ansible.zip`. Again, you do not want to zip up the folder itself!

Finally, create the final zip file. It should be called `sandbar.zip`, and it should contain: the `sandbar-source.zip` file; the `sandbar-ansible.zip` file; the `config.yml` file; the `sandbar-deploy.sh` and `sandbar-update.sh` scripts; and finally (as well as optionally) the `readme.md` file.

This is the completed `sandbar.zip`! You can upload it to the destination server and install it using the commands specified above.

## Connecting a Sandbar to the Git repo for development

The first step is to make sure git is installed and that the server has access to the repository. You can use SSH key access or HTTP access.

Create a folder called `sandbar-source` in the `~/sandbar/` folder, and clone the git repository inside it with the command below (assuming SSH access):

> `git clone git@bitbucket.org:xander-sereda/sandbar.git .`

The command below runs the usual git commands to update the code, zips the directory up so that it replaces the existing `sandbar-source.zip`:

> `git fetch && git reset --hard origin/dev && zip -r ../sandbar-source.zip ./*`

Then, all you have to do is run the update script!

> `sudo sh sandbar-update.sh 2>&1 | sudo tee -a /var/log/sandbar-update.log`

Putting that together, we have:

> `cd ~/sandbar/sandbar-source && git fetch && git reset --hard origin/dev && rm ~/sandbar/sandbar-source.zip && zip -r ~/sandbar/sandbar-source.zip  ./* && cd ~/sandbar && sudo sh sandbar-update.sh 2>&1 | sudo tee -a /var/log/sandbar-update.log`

Do keep in mind that if the Django config file or other ansible-deployment files have been changed, there is additional step:

> `rm ~/sandbar/sandbar-ansible.zip && cd ~/sandbar/sandbar-source/ansible-deployment/sandbar-ansible/ && zip -r ~/sandbar/sandbar-ansible.zip  ./*`

The command below updates BOTH the source code and the deployment scripts

> `cd ~/sandbar/sandbar-source && git fetch && git reset --hard origin/dev && rm ~/sandbar/sandbar-source.zip && zip -r ~/sandbar/sandbar-source.zip  ./* && rm ~/sandbar/sandbar-ansible.zip && cd ~/sandbar/sandbar-source/ansible-deployment/sandbar-ansible/ && zip -r ~/sandbar/sandbar-ansible.zip  ./* && cd ~/sandbar && sudo sh sandbar-update.sh 2>&1 | sudo tee -a /var/log/sandbar-update.log`


## Updating a Sandbar Instance

A completed installation of sandbar should have an "installation" folder somewhere (usually a user's home folder), which contains the contents of the `sandbar.zip` file. Any of these contents can be updated simply by overwriting them with new versions, but in order to **apply** these updates to the existing sandbar installation, you must run the following command:

> `sudo sh sandbar-update.sh 2>&1 | sudo tee -a /var/log/sandbar-update.log`

* Contents of sandbar-ansible.zip have the subfolders and files that will end up in /etc/ansbile. It's imperative the folders and files are in the root of the zip file.
* If the server must pass web traffic through a proxy, you'll need to add that configuration. Otherwise you will be unable to download the required packages. Please see: http://askubuntu.com/questions/175172/how-do-i-configure-proxies-without-gui

Single liner to deploy (assumes config.yml defaults)
* sudo apt-get install unzip && unzip sandbar.zip && sudo sh sandbar-deploy.sh 2>&1 | sudo tee -a /var/log/sandbar-deploy.log

## Misc manual commands

If you need to activate the virtualized python enviroment, first SU into the sandbar user, and then:

> `source ./venv/bin/activate`



## Manual Installation (incomplete)

1. Get the latest code from Bitbucket.
2.
2. In the project folder, use `vituralenv` to create a localized bundle of Python (so you are not using the global python install)
3. Activate (i.e. start using) the bundle with `source ./env/bin/activate`, and turn it off with `deactivate`
4. Dependencies are stored in a file called `req.ext` - load/install them by `pip install -r req.txt`. To generate such a list yourself, use `pip freeze req.txt`

## Deployment and/or Testing

Setting up NGINX, UWSGI, Celery, Rabbit, and Django is a complex task, and it is not for the faint of heart!

Begin by reading this guide: https://www.digitalocean.com/community/tutorials/how-to-serve-django-applications-with-uwsgi-and-nginx-on-ubuntu-14-04

1. Each project has its own "runtime bundle" of python and python packages. You can activate this using `workon sandbar_dev` or `workon sandbar`, or manually like this: `source ~/Env/sandbar_dev/bin/activate`.
2. `./manage.py makemigrations`
1. `python manage.py migrate` to run the DB migrations, if any
2. `python manage.py runserver 0.0.0.0:3000` to run the "test" server, which will only be accessible from the VLAN
3. Access it at `http://192.168.10.55:3000/`

You can also run the application in testing mode with UWSGI: `nohup python manage.py runserver 0.0.0.0:3000 & uwsgi --http :8001 --home /home/rhino/Env/sandbar --chdir /home/rhino/sandbar -w sandbar.wsgi`

### Testing

1. Install the test requirements:
`$ pip install -r requirements/test.txt`
2. Create the test database:
`$ createdb sandbar_test`
`$ psql postgres`
`postgres=# CREATE ROLE sandbar_test_owner WITH PASSWORD '1234567' CREATEDB;`
`postgres=# GRANT ALL ON DATABASE sandbar_test TO sandbar_test_owner;`
`postgres=# ALTER DATABASE sandbar_test OWNER TO sandbar_test_owner;`
`postgres=# \q`
3. Call the Django test runner:
`$ ./manage.py test`
