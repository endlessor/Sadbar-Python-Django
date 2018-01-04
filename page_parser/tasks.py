from celery import task
from celery.utils.log import get_task_logger
from page_parser.views import PageParser
from os.path import join as join_path


logger = get_task_logger(__name__)


@task
def parse_page(landingPage):
    url = landingPage.url.encode('utf-8')

    if landingPage.scraper_user_agent is not None:
        user_agent = landingPage.scraper_user_agent.user_agent_data
    else:
        user_agent = ''

    dirname = '{}-{}'.format(landingPage.id,
                             landingPage.date_created.strftime('%s'))
    directory = join_path('assets', 'landing-pages', dirname)
    if landingPage.is_redirect_page:
        directory = directory.replace('landing-pages', 'redirect-pages')

    parser = PageParser(url, user_agent, directory)
    try:
        page_path = parser.parse_page()
        landingPage.path = page_path
        landingPage.status = 1
    except Exception as error:
        logger.info('[ ! ] parse_page task for LandingPage #{} failed with'
                    ' exception: {}'.format(landingPage.id, error))
        landingPage.status = 3
    landingPage.save()
