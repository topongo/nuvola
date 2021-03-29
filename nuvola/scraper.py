import seleniumwire.webdriver
import requests
from json.decoder import JSONDecodeError
from simplejson.decoder import JSONDecodeError as JSONDecodeError_

opt = seleniumwire.webdriver.ChromeOptions()
opt.headless = True
opt.add_argument("start-maximized")
opt.add_argument("enable-automation")
opt.add_argument("--headless")
opt.add_argument("--no-sandbox")
opt.add_argument("--disable-infobars")
opt.add_argument("--disable-dev-shm-usage")
opt.add_argument("--disable-browser-side-navigation")
opt.add_argument("--disable-gpu")


class InvalidCredentialsException(Exception):
    pass


class ExpiredSessionTokenException(Exception):
    pass


class GenericErrorException(Exception):
    pass


def scrape_from_token(session_token, verb=False):
    try:
        if verb:
            print("\n:: Scraper :: Trying to get auth_token...")
        return requests.get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                   cookies={"nuvola": str(session_token)}).json()["token"]
    except (JSONDecodeError, JSONDecodeError_):
        if verb:
            print(":: Scraper :: Failed to get auth_token: session_token is not invalid.")
        raise ExpiredSessionTokenException


def scrape_from_credentials(user, pwd, verb=False):
    if verb:
        print("\n:: Scraper :: Starting driver...")
    d = seleniumwire.webdriver.Chrome(chrome_options=opt)
    if verb:
        print(":: Scraper :: Getting login page...")
    d.get("https://nuvola.madisoft.it/login/")
    d.find_element_by_id("username").send_keys(user)
    d.find_element_by_id("password").send_keys(pwd)
    d.find_elements_by_tag_name("button")[1].click()
    if verb:
        print(":: Scraper :: Logging in...")
    if "https://nuvola.madisoft.it/area-studente" not in [i.url for i in d.requests]:
        if verb:
            print(":: Scraper :: Login failed.")
        d.close()
        raise InvalidCredentialsException

    if verb:
        print(":: Scraper :: Authentication successful.")
    session_token = d.get_cookie("nuvola")["value"]
    d.close()

    try:
        if verb:
            print(":: Scraper :: Trying to get auth_token...")
        r = requests.get("https://nuvola.madisoft.it/api-studente/v1/login-from-web",
                         cookies={"nuvola": str(session_token)})
        return session_token, r.json()["token"]
    except (JSONDecodeError, JSONDecodeError_):
        if verb:
            print(":: Scraper :: Something has gone wrong.")
        raise InvalidCredentialsException
