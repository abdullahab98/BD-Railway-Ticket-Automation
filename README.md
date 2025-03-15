create .env {
#Credential
MOBILE_NUMBER =01780879898
PASSWORD =a1412805688

#Travel Details
FROM_CITY =Dhaka
TO_CITY = Parbatipur
DATE_OF_JOURNEY =16-Mar-2025
SEAT_CLASS =S_CHAIR
TRAIN_NUMBER =705
MAX_SELECTABLE_SEAT =2

#Desired Seats(comma separated)
DESIRED_SEATS =
}

pacages
{
import requests, time, os, aiohttp, asyncio, re
import jwt
from jwt import ExpiredSignatureError, DecodeError
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from colorama import Fore
import ssl
}
