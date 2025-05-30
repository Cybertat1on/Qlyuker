from ua_generator import generate
from ua_generator.options import Options
from ua_generator.data.version import VersionRange


def generate_random_user_agent(platform: str = 'android', browser: str = 'chrome', 
                                min_version: int = 110, max_version: int = 129) -> str:
    options = Options(version_ranges={'chrome': VersionRange(min_version, max_version)})
    return generate(browser=browser, platform=platform, options=options).text
