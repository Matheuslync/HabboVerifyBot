# Bot configuration file
# This file contains all configurable settings for the Discord verification bot

# Bot settings
PREFIX = '!'  # Command prefix
VERIFY_COMMAND = 'verify'  # Command to start verification
CODE_PREFIX = 'myt-'  # Verification code prefix
EXPIRATION_TIME = 5 * 60  # Expiration time in seconds (default: 5 minutes)
VERIFICATION_INTERVAL = 5  # Interval between verifications in seconds
VERIFIED_ROLE = 'Verified'  # Role name to be assigned
CHANGE_NICKNAME = True  # Controls whether the bot should change user's nickname after verification
SERVER_OPTION = 'habbo.com.br'  # Habbo server option (available: habbo.com / habbo.com.br / habbo.es / habbo.de)

# Verification image settings
VERIFICATION_TEXT = "Welcome \nto MYT!"  # Text displayed below username
BACKGROUND_COLOR = (20, 20, 20)  # Default background color if not using image
BACKGROUND_IMAGE = "background.png"  # Path to custom background image
CUSTOM_FONT = "Montserrat.ttf"  # Path to custom font
FONT_SIZE = 24  # Font size
MAIN_TEXT_COLOR = (255, 255, 255)  # Main text color
SECONDARY_TEXT_COLOR = (255, 181, 77)  # Secondary text color