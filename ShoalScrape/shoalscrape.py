#!/usr/bin/python
try:
    from selenium import webdriver
except:
    print "This script requires selenium webserver to be running along with selenium webdriver."
    print "For linux distributions, please run the install script located in the top \
           level directory."
    raise SystemExit
import optparse
from tempfile import mkstemp
from time import sleep
from random import randint
from datetime import datetime
import socket
import smtplib
import dns.resolver
import commands
import signal
import os
import sys
import itertools
import re
import csv

from django.conf import settings


log_file = ""


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_red(string):
    print "{}{}{}".format(bcolors.FAIL, string, bcolors.ENDC)

def print_green(string):
    print "{}{}{}".format(bcolors.OKGREEN, string, bcolors.ENDC)

def print_yellow(string):
    print "{}{}{}".format(bcolors.WARNING, string, bcolors.ENDC)

def print_blue(string):
    print "{}{}{}".format(bcolors.OKBLUE, string, bcolors.ENDC)

def print_underline(string):
    print "{}{}{}".format(bcolors.UNDERLINE, string, bcolors.ENDC)

def print_bold(text):
    print "{}{}{}".format(bcolors.BOLD, text, bcolors.ENDC)

def print_header(text):
    print "{}{}{}".format(bcolors.FAIL, text, bcolors.ENDC)

def to_str(string):
    if isinstance(string, unicode):
        return string.encode('utf-8')
    elif isinstance(string, bytes):
        return string.decode('utf-8')
    else:
        return string


class LinkedInSession(object):
    """
    Manages a site session given a username, password and website.
    """

    # EXPERIENCE SELECTORS
    # ---------------------------------------------
    # Experience container ID on profile page
    experience_container_id = 'background-experience-container'
    # Education container ID on profile Page
    education_container_id = "background-education-container"
    # To find all experience containers on page.
    regex_exp_id = "(experience-[0-9]+-view)"
    # To find all education containers on page.
    regex_edu_id = "(education-[0-9]+-view)"
    # Name of position tag element
    title_section_tag = "header"
    title_detail = "h4"
    # Dates they held position
    exp_date_detail = 'span[class="experience-date-locale"]'
    edu_date_detail = 'span[class="education-date"]'
    # Long form explanation of each position here
    background_detail = 'p[class="description summary-field-show-more"]'
    # Long form explanation of each education
    education_detail = 'p[class="notes summary-field-show-more"]'

    # SKILLS SELECTORS
    # ---------------------------------------------
    # Covers all skills
    skills_container_id = "profile-skills"
    # Gets list of skills
    skills_selector = 'span[class="endorse-item-name"]'

    # PROFILE PAGE SELECTORS
    # ---------------------------------------------
    # The contact information display toggle
    contact_button_class = '.contact-see-more-less'
    # The element containing the profile photo
    photo_wrapper_class = '.pv-top-card-section__photo'

    # SEARCH PAGE SELECTORS
    # ---------------------------------------------
    # Finds profile links
    search_link_class = '.search-result__result-link'
    # Finds short details on each
    summary_container_class = '.search-result--person'
    # Finds the "Next" button on search result pages
    next_page_class = 'button[class="next"]'

    # STATIC URLS / TEXT
    # ----------------------------------------------
    # LinkedIn website page
    landing_url = "https://www.linkedin.com"
    # Search url to parse results
    search_url = 'https://www.linkedin.com/search/results/people/?facetCurrentCompany=%5B"{}"%5D&page={}'
    # Login url to post to
    login_url = "https://www.linkedin.com/uas/login-submit"
    # Lets us know if the member is out of network and cannot perform more parsing
    out_of_net = "Profile summaries for members outside your network are available only to premium account holders"

    # Account credentials
    # ----------------------------------------------
    username = "linkedin.account.email@goes.here"
    password = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

    def __init__(self, webdriver_path, log_file, user_agent,
                 username=None, password=None, managed_webdriver=None):
        self.webdriver_path = webdriver_path
        if username and password:
            self.username = username
            self.password = password
        # NB: log_file must be an opened file with 'w+b' flags.
        # It should be context-managed to the scope that calls LinkedInSession.
        self.log_file = log_file
        if user_agent is not None:
            self.user_agent = user_agent
        else:
            self.user_agent = 'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.2; .NET CLR 1.1.4322)'
        if managed_webdriver is not None:
            self.driver = managed_webdriver
        else:
            try:
                self.driver = webdriver.PhantomJS(self.webdriver_path)
            except Exception, e:
                usage()
        self.driver.set_window_size(1120, 550)

    def login(self):
        # print  "{}[ + ] Logging in...{}".format(bcolors.OKGREEN, bcolors.ENDC)
        self.log_file.write("[ + ] Logging in...\n")
        self.load_page("https://www.linkedin.com/")
        self.driver.find_element_by_id('login-email').send_keys(self.username)
        self.driver.find_element_by_id('login-password').send_keys(self.password)
        self.driver.find_element_by_css_selector('input[value="Sign in"]').click()

    def load_page(self, url, count=None):
        try:
            self.driver.get(url)
            return
        except Exception, e:
            # print  '{}[ - ] {}\n\tError loading page {}. Is selenium webserver running? Retrying...{}'.format(bcolors.FAIL,e, url,bcolors.ENDC)
            self.log_file.write('[ - ] {}\n\tError loading page {}. Is selenium webserver running? Retrying...\n'.format(e, url))
            sleep(15)
            if count is None:
                count = 1
            else:
                count += 1
            if count > 3:
                return False
            # print  "{}Retrying {} more times...{}".format(bcolors.WARNING, 3 - count, bcolors.ENDC)
            self.log_file.write("Retrying {} more times...\n".format(3 - count))
            return self.load_page(url, count)

    def get_search_results(self, company, company_id):
        counter = 1
        results = []
        next_page = True
        while next_page is True:
            url = self.search_url.format(company_id, counter)
            self.load_page(url)

            # print  "{}[ + ] Parsing page {} of search resultsusing URL {}{}".format(bcolors.OKBLUE,counter,url,bcolors.ENDC)
            self.log_file.write("[ + ] Parsing page {} of search results using URL {}\n".format(counter, url))

            page_results = list()
            for each in range(3):
                if page_results:
                    continue
                else:
                    page_results = self.fetch_page_results(company)
                    if not page_results:
                        # print  "{}[ - ] Unable to parse page {} of search results; sleeping for 5s before retrying.{}".format(bcolors.OKBLUE,counter,bcolors.ENDC)
                        self.log_file.write("[ - ] Unable to parse page {} of search results; sleeping for 5s before retrying.\n".format(counter))
                        sleep(5)

            if not page_results:
                # print  "{}[ ! ] Page {} of search results failed to load.{}".format(bcolors.WARNING,counter,bcolors.ENDC)
                self.log_file.write("[ ! ] Page {} of search results failed to load.\n".format(counter))
            else:
                results += page_results

            counter += 1
            # Might need this sleep to prevent search throttling
            lower = randint(30,35)
            higher = randint(50,60)
            zzz = randint(lower, higher)
            # print  "[ - ] Sleeping {}".format(zzz)
            self.log_file.write("[ - ] Sleeping {}\n".format(zzz))
            sleep(zzz)
            next_page = self.has_next()

        self.src_to_file()
        return results

    def has_next(self):
        try:
            n = self.driver.find_element_by_css_selector(self.next_page_class)
            # print "\"Next Page\" button successfully found...\n"
            self.log_file.write("\"Next Page\" button successfully found...\n")
            if n:
                return True
            return False
        except:
            # print  "[DEBUG] Could not find the next button."
            self.log_file.write("Could not find the next button.\n")
            return False

    def fetch_page_results(self, company):
        results = self.driver.find_elements_by_css_selector(self.summary_container_class)
        results = self.parse_summaries(results, company)
        if results:
            return results
        else:
            return []

    def parse_profiles(self, results):
        browser_window_height = self.driver.get_window_size()[1]

        for result in results:
            if result['profile_link']:
                self.load_page(result['profile_link'])
                result['email'] = []

                try:
                    # LinkedIn profile pages now load when scrolled down.
                    # (If one scroll to max height doesn't work, this may need
                    # to be repeated an unknown number of times.)
                    # Reference: http://stackoverflow.com/a/27760083
                    previous_scroll_height = browser_window_height
                    for each_scroll_down in range(10):
                        # Ensure nothing is skipped by scrolling down five pixels
                        # fewer than the height of the window.
                        self.driver.execute_script('window.scrollTo(0, {});'.format(browser_window_height - 5))

                        self.driver.execute_script('console.log(document.body.scrollHeight);')
                        current_scroll_height = self.driver.get_log('browser')[0]['message'].split(' ')[0]

                        if int(current_scroll_height) > int(previous_scroll_height):
                            previous_scroll_height = current_scroll_height
                        else:
                            break
                        # Let the page load
                        sleep(1)
                except:
                    pass

                try:
                    self.driver.find_element_by_css_selector(self.contact_button_class).click()
                    sleep(4)
                    emails = self.driver.find_element_by_css_selector('a[href^="mailto:"]').text
                    if emails:
                        # print  "[ + ] Email found: {}".format(emails)
                        self.log_file.write("[ + ] Email found: {}\n".format(emails))
                        result['email'] = emails.split('\n')
                    else:
                        # print  "[ + ] Email not found for {}".format(result['name'])
                        self.log_file.write("[ + ] Email not found for {}\n".format(result['name']))
                        result['email'] = ''
                except Exception, e:
                    # print  "{}[ - ] An error occured while parsing emails: {}".format(bcolors.FAIL, e, bcolors.ENDC)
                    self.log_file.write("[ - ] An error occured while parsing emails: {}\n".format(e))
                    pass

                try:
                    result['picture_url'] = self.driver.find_element_by_class_name(self.photo_wrapper_class).find_element_by_tag_name("img").get_attribute("src").encode('utf-8')
                except Exception, e:
                    result['picture_url'] = ''

                result["experience"] = self.parse_experience()
                result["education"] = self.parse_education()
                result["skills"] = self.parse_skills()

            else:
                result['email'] = ""
                result['experience'] = []
                result['skills'] = []
                result['education'] = []

        # print  "{}[ + ] Finished parsing the profile of {}".format(bcolors.FAIL, result['name'], bcolors.ENDC)
        self.log_file.write("[ + ] Finished parsing the profile of {}\n".format(result['name']))

        return results

    def parse_education(self):
        edu_list = []
        edu_selectors = re.findall(self.regex_edu_id, self.driver.page_source)
        if not edu_selectors:
            return edu_list
        edu_container = self.driver.find_element_by_id(self.education_container_id)
        for s in edu_selectors:
            details = {
                "school":"",
                "degree":"",
                "dates":"",
                "description":"",
            }
            edu = edu_container.find_element_by_id(s)
            try:
                details['dates'] = to_str(edu.find_element_by_css_selector(self.edu_date_detail).text)
            except Exception, e:
                pass
            try:
                details["school"] = to_str(edu.find_element_by_css_selector("header > h4 > a").text)
            except Exception, e:
                pass
            try:
                details["degree"] = to_str(edu.find_element_by_css_selector("header > h5").text)
            except Exception, e:
                pass
            try:
                details["description"] = to_str(edu.find_element_by_css_selector(self.education_detail).text)
            except Exception, e:
                pass
            edu_list.append(details)
        return edu_list

    def parse_experience(self):
        exp_list = []
        exp_selectors = re.findall(self.regex_exp_id, self.driver.page_source)
        if not exp_selectors:
            return exp_list
        exp_container = self.driver.find_element_by_id(self.experience_container_id)
        for s in exp_selectors:
            details = {
                "title":"",
                "dates":"",
                "company":"",
                "description":"",
            }
            exp = exp_container.find_element_by_id(s)
            try:
                details['dates'] = to_str(exp.find_element_by_css_selector(self.exp_date_detail).text)
            except Exception, e:
                pass
            try:
                details['title'] = to_str(exp.find_element_by_css_selector('header > h4').text)
            except Exception, e:
                pass
            try:
                details['company'] = to_str(exp.find_element_by_css_selector("header > h5 > span > strong").text)
            except Exception,e:
                pass
            try:
                details['description'] = to_str(exp.find_element_by_css_selector(self.background_detail).text)
            except Exception, e:
                pass
            exp_list.append(details)
        return exp_list

    def parse_skills(self):
        skills_list = []
        try:
            container = self.driver.find_element_by_id(self.skills_container_id)
            skills = container.find_elements_by_css_selector(self.skills_selector)
            for skill in skills:
                try:
                    skills_list.append(to_str(skill.text))
                except Exception, e:
                    pass
            return skills_list
        except Exception, e:
            # print  "{}[ - ] An error occured while parsing skills: {}{}".format(bcolors.FAIL,e,bcolors.ENDC)
            self.log_file.write("[ - ] An error occured while parsing skills: {}\n".format(e))

    def parse_summaries(self, results, company):
        employee_list = []
        for result in results:
            employee_map = {}
            text = result.text.split('\n')

            # Name mapping
            name = to_str(text[0])
            if name == 'LinkedIn Member':
                # print  "{}[ - ] Skipping {}...{}".format(bcolors.OKGREEN, name, bcolors.ENDC).encode('utf-8', 'ignore')
                self.log_file.write("[ - ] Skipping {}...\n".format(name).encode('utf-8', 'ignore'))
                continue

            employee_map['name'] = text[0]
            employee_map['title'] = result.find_element_by_css_selector('.subline-level-1').text
            employee_map['location'] = result.find_element_by_css_selector('.subline-level-2').text

            try:
                employee_map["profile_link"] = result.find_elements_by_css_selector(self.search_link_class)[0].get_attribute('href')
            except Exception, e:
                # print  "[ - ] Couldn't find profile link. ??"
                self.log_file.write("[ - ] Couldn't find profile link. ??\n")
                employee_map["profile_link"] = ""

            try:
                # print  "{}[ + ] Adding {} to the list of employees...{}".format(bcolors.OKGREEN, employee_map['name'], bcolors.ENDC).encode('utf-8', 'ignore')
                self.log_file.write("[ + ] Adding {} to the list of employees...\n".format(employee_map['name']).encode('utf-8', 'ignore'))
                employee_list.append(employee_map)
            except Exception, e:
                # print  "{}[ ! ] Could not parse this employee: {}. Dwight sucks at unicode...{}".format(bcolors.FAIL, employee_map['profile_link'], bcolors.ENDC)
                self.log_file.write("[ ! ] Could not parse this employee: {}. Dwight sucks at unicode...\n".format(employee_map['profile_link']))

        return employee_list

    def src_to_file(self):
        s, fp = mkstemp(suffix=".html")
        with open(fp, "r+b") as out:
            out.write(self.driver.page_source.encode('utf-8', 'ignore'))
        # print  "{}[ + ] This page source can be found at {}.{}".format(bcolors.BOLD,fp,bcolors.ENDC)
        self.log_file.write("[ + ] This page source can be found at {}.\n".format(fp))

    def write_results(self, storage_path, results):
        a = commands.getoutput("mkdir {}".format(storage_path))
        master_csv = storage_path + "/master_list.csv"
        with open(master_csv, 'w+b') as out:
            dict_writer = csv.DictWriter(out, results[0].keys())
            dict_writer.writeheader()
            dict_writer.writerows(results)
        employee_csv = storage_path + "/{}.csv"
        employee_txt = storage_path + "/{}.txt"
        counter = 0
        for r in results:
            f_name = r['name'].lower().replace(" ", "_")
            if f_name == "linkedin_member":
                e_csv = employee_csv.format("{}_{}".format(f_name, counter))
                e_txt = employee_txt.format("{}_{}".format(f_name, counter))
                counter += 1
            else:
                e_csv = employee_csv.format(f_name)
                e_txt = employee_txt.format(f_name)
            self.write_individual_csv(e_csv, r)
            self.write_individual_txt(e_txt, r)
        # print  "{}[ + ] A full list of employee information can be found here: {}{}".format(bcolors.OKGREEN, storage_path, bcolors.ENDC)
        self.log_file.write("[ + ] A full list of employee information can be found here: {}\n".format(storage_path))

    def webserver_write_results(self, storage_path, master_csv_filename, results):
        a = commands.getoutput("mkdir {}".format(storage_path))
        master_csv = os.path.join(storage_path, master_csv_filename)

        ascii_encoded_results = list()
        for each in results:
            new_result = dict()
            for key, value in each.items():
                new_key = key.encode('ascii', 'ignore')
                new_value = value.encode('ascii', 'ignore')
                new_result[new_key] = new_value
            ascii_encoded_results.append(new_result)

        with open(master_csv, 'w+b') as out:
            dict_writer = csv.DictWriter(out, ascii_encoded_results[0].keys())
            dict_writer.writeheader()
            dict_writer.writerows(ascii_encoded_results)
        # print  "{}[ + ] A full list of employee information can be found here: {}{}".format(bcolors.OKGREEN, storage_path, bcolors.ENDC)
        self.log_file.write("[ + ] A full list of employee information can be found here: {}\n".format(storage_path))

    def write_individual_csv(self, filename, result):
        with open(filename, "w+b") as f:
            dict_writer = csv.DictWriter(f, result.keys())
            dict_writer.writeheader()
            dict_writer.writerow(result)

    def write_individual_txt(self, filename, result):
        with open(filename, "w+b") as f:
            for k, v in result.items():
                f.write("\n--- " + k.replace("_", " ").title() + " ---\n")
                if type(v) == list:
                    for l in v:
                        if type(l) == dict:
                            f.write("\n")
                            for k2, v2 in l.items():
                                f.write("{}: {}\n".format(k2,v2))
                            f.write("\n")
                        else:
                            f.write("\n{}\n".format(l))
                else:
                    f.write("\n{}\n".format(v))

    def search(self, company, company_id):
        r = self.get_search_results(company, company_id)
        return r

    def smtp_brute(self, people, domain):
        records = dns.resolver.query(domain, 'MX')
        mxRecord = records[0].exchange
        mxRecord = str(mxRecord)

        # Avoid wasting time with incorrect MX records:
        host = socket.gethostname()
        server = smtplib.SMTP()
        server.set_debuglevel(0)
        try:
            server.connect(mxRecord)
        except IOError as e:
            # print("[ ! ] MX record '{}' raised an IO error: {}\n".format(mxRecord, e))
            self.log_file.write("[ ! ] MX record '{}' raised an IO error on first check: {}\n".format(mxRecord, e))
            server.quit()
            return people

        for p in people:
            valid_emails = []
            host = socket.gethostname()
            server = smtplib.SMTP()
            server.set_debuglevel(0)
            try:
                server.connect(mxRecord)
                server.helo(host)
                server.mail("corn@bt.com")
                name = p['name']
                emails = self.create_emails(name, domain)
                for e in emails:
                    if self.verify(server, e):
                        valid_emails.append(e)
                p['email'] += valid_emails
            # In case the MX starts timing out part of the way through:
            except IOError:
                # print("[ ! ] MX record '{}' raised an IO error: {}\n".format(mxRecord, e))
                self.log_file.write("[ ! ] MX record '{}' raised an IO error: {}\n".format(mxRecord, e))
            server.quit()
        return people

    def create_emails(self, name, domain):
        emails = []
        # some basic name sanitization. Basically
        # want the form of FIRST MID LAST or FIRST LAST
        if "," in name:
            name = name.split(",")[0].strip()
        name = name.replace("(","").replace(")","").replace(".","").strip()
        names = name.split(" ")
        length = len(names)
        names = [n.lower() for n in names]
        names += [n.replace("-","") for n in names if "-" in n]
        # add initials
        names += [n[0] for n in names if n[0] not in names]
        emails += list(set(self.perm(names, domain, length)))
        return emails

    def perm(self, names, domain, repeat):
        emails = []
        if repeat == 1:
            for n in names:
                emails.append("{}@{}".format(n, domain))
        else:
            for i in xrange(repeat):
                r = i+1
                perms = itertools.combinations(names, r)
                str1 = "%s"*r + "@{}".format(domain)
                str2 = "%s."*r
                str2 = str2[:-1] + "@{}".format(domain)
                # str3 = "%s_"*r
                # str3 = str3[:-1] + "@{}".format(domain)
                # str4 = "%s-"*r
                # str4 = str4[:-1] + "@{}".format(domain)
                for p in perms:
                    emails.append(str1 % p)
                    emails.append(str2 % p)
                    # emails.append(str3 % p)
                    # emails.append(str4 % p)
        return emails

    def verify(self, server, email):
        code, message = server.rcpt(email)
        # print email, code
        if code == 250 or code == 450:
            self.log_file.write('[ + ] {} {}\n'.format(email, code))
        else:
            self.log_file.write('[ - ] {} {}\n'.format(email, code))
        return code == 250 or code == 450


def usage():
    print "{}Rhino Security Labs{}".format(bcolors.FAIL, bcolors.ENDC)
    print "Usage:"
    print '       ./shoalscrape.py -c "Acme Inc." -d "acmeinc.com" -i "000000"'
    print "Variables:"
    print "        company_name: Company name you wish to search for. e.g. 'Rhino Security Labs'"
    print "Notes:"
    print "      - Basic users are rate throttled with how much they can actually search users."
    print "****** LINUX USERS *******"
    print "Please run the install shell script if this is your first time cloning the package."
    raise SystemExit


def main():
    if sys.argv[1] == "--help":
        usage()
    parser = optparse.OptionParser('./shoalscrape.py -c "Acme Inc."')
    parser.add_option('-c', dest='company', type='string', help='Company to search for employees on LinkedIn.')
    parser.add_option('-d', dest='domain', type='string', help='Domain of company.')
    parser.add_option('-i', dest='company_id', type='string', help='LinkedIn company ID number.')
    parser.add_option('-p', dest='scan_profiles', type='string', help='Whether or not to scan profiles for additional user data. y/n (default: n)')
    parser.add_option('-b', dest='brute_force_emails', type='string', help='Whether or not to attempt to find emails via brute force checking. y/n (default: n)')
    (options, args) = parser.parse_args()
    if not options.company:
        usage()
    if not options.domain:
        usage()
    if not options.company_id:
        usage()

    try:
        scan_profiles = options.scan_profiles.lower()[0] == 'y'
        brute_force_emails = options.brute_force_emails.lower()[0] == 'y'
    except:
        scan_profiles = False
        brute_force_emails = False

    storage_path = os.path.join(settings.SHOALSCRAPE_RESULTS_PATH, options.company.lower().replace(" ", "_"))
    if not os.path.exists(storage_path):
        os.makedirs(storage_path)

    now = datetime.now()

    log_file_name = os.path.join(storage_path, "{}_{}_{}d_{}h_{}m.log".format(now.year, now.month, now.day, now.hour, now.minute))

    with open(log_file_name, 'w+b') as log_file:
        print "[ + ] Logging results to {}".format(log_file_name)
        session = LinkedInSession(settings.PHANTOMJS_PATH, log_file)
        session.login()
        print "{}[ + ] We will crawl LinkedIn for: {}{}".format(bcolors.OKGREEN, options.company.title(), bcolors.ENDC)
        results = session.search(options.company, options.company_id)
        print "Final length of summary results: {}".format(len(results))
        if results:
            session.write_results(storage_path, results)

        if scan_profiles:
            results = session.parse_profiles(results)
            if results:
                session.write_results(storage_path, results)

        if brute_force_emails:
            try:
                results = session.smtp_brute(results, options.domain)
                if results:
                    session.write_results(storage_path, results)
            except IOError as e:
                print("[ ! ] Could not brute force email addresses: {}\n".format(e))


class TimestampedRealTimeFileWriter(object):

    def __init__(self, file_path, flags):
        self.file_path = file_path
        # If flags has 'w' instead of 'a' it's nearly pointless, but permitted.
        self.flags = flags

    def write(self, data):
        with open(self.file_path, self.flags) as file_handler:
            timestamped_data = '[{}] {}'.format(datetime.now(), data)
            file_handler.write(timestamped_data)


def webserver_main(company, company_id, domain, log_file_path, user_agent, username=None, password=None, scan_profiles=False, brute_force_emails=False):
    storage_path = os.path.dirname(log_file_path)
    # File must be opened in append mode.
    log_file = TimestampedRealTimeFileWriter(log_file_path, 'a+b')

    driver = webdriver.PhantomJS(settings.PHANTOMJS_PATH)

    # reference: https://nattster.wordpress.com/2013/06/05/catch-kill-signal-in-python/
    def signal_term_handler(_signal, *args, **kwargs):
        driver.close()
        driver.quit()
        raise SystemExit
    signal.signal(signal.SIGTERM, signal_term_handler)

    session = LinkedInSession(settings.PHANTOMJS_PATH, log_file, user_agent, username=username, password=password, managed_webdriver=driver)

    # print("[ + ] Logging results to {}\n".format(log_file_path))
    session.log_file.write("[ + ] Logging results to {}\n".format(log_file_path))
    session.login()
    # print ("{}[ + ] We will crawl LinkedIn for: {}{}\n".format(bcolors.OKGREEN, company.title(), bcolors.ENDC))
    session.log_file.write("[ + ] We will crawl LinkedIn for: {}\n".format(company.title()))

    results = session.search(company, company_id)
    results_length = len(results)
    # print ("Final length of summary results: {}\n".format(results_length))
    session.log_file.write("Final length of summary results: {}\n".format(results_length))

    master_csv_filename = '{}_master_list.csv'.format(company.lower().replace(" ", "_"))
    if results:
        session.webserver_write_results(storage_path, master_csv_filename, results)

    if scan_profiles:
        results = session.parse_profiles(results)
        # Update the file with profile data by overwriting its contents.
        if results:
            session.webserver_write_results(storage_path, master_csv_filename, results)
    else:
        # print("[ - ] Skipping profile page parsing.\n")
        session.log_file.write("[ - ] Skipping profile page parsing.\n")

    if brute_force_emails:
        try:
            results = session.smtp_brute(results, domain)
            if results:
                session.webserver_write_results(storage_path, master_csv_filename, results)
        except Exception as e:
            # print("[ ! ] Could not brute force email addresses: {}\n".format(e))
            session.log_file.write("[ ! ] Could not brute force email addresses: {}\n".format(e))
    else:
        # print("[ - ] Skipping email address brute forcing.\n")
        session.log_file.write("[ - ] Skipping email address brute forcing.\n")

    try:
        driver.close()
        driver.quit()
    except:
        pass
    session.log_file.write("[ . ] ShoalScrape task for company {} with domain {} successfully completed.\n".format(company, domain))

    return results_length


if __name__ == '__main__':
    main()
