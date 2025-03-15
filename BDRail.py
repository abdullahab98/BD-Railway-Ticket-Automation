import requests, time, os, aiohttp, asyncio, re
import jwt
from jwt import ExpiredSignatureError, DecodeError
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from colorama import Fore
import ssl

# Load environment variables from .env file
load_dotenv()

# Read values from the environment
mobile_number = os.getenv("MOBILE_NUMBER")
password = os.getenv("PASSWORD")

from_city = os.getenv("FROM_CITY")
to_city = os.getenv("TO_CITY")
date_of_journey = os.getenv("DATE_OF_JOURNEY")
seat_class = os.getenv("SEAT_CLASS")
train_number = int(os.getenv("TRAIN_NUMBER"))
max_selectable_seat = int(os.getenv("MAX_SELECTABLE_SEAT"))

# Convert the desired seats from a comma-separated string to a list
desired_seats = os.getenv("DESIRED_SEATS").split(',') if os.getenv("DESIRED_SEATS") else []

# Function to fetch auth token dynamically
def fetch_auth_token(mobile_number, password):
    login_url = "https://railspaapi.shohoz.com/v1.0/app/auth/sign-in"
    payload = {
        "mobile_number": mobile_number,
        "password": password
    }

    while True:
        try:
            response = requests.post(login_url, data=payload)

            if response.status_code == 200:
                data = response.json()
                auth_token = data.get("data", {}).get("token")
                if auth_token:
                    print(f"{Fore.GREEN}Authentication successful!")
                    print(f"{Fore.MAGENTA}Auth Token: {auth_token}")
                    return auth_token
                else:
                    print(f"{Fore.RED}Failed to retrieve token from response.")
                    return None

            elif response.status_code in [500, 502, 503, 504]:
                print(f"{Fore.YELLOW}Server overloaded (HTTP {response.status_code}). Retrying in 1 second...")
                time.sleep(1)
                
            else:
                print(f"{Fore.RED}Error: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
                print(f"{Fore.RED}Exception occurred while fetching auth token: {e}")
                time.sleep(1)  # Retry after 1 second in case of an exception

def extract_user_info_from_token(): 
    try:
        # Decode the JWT token without verifying signature (for debugging only)
        decoded_token = jwt.decode(auth_key, options={"verify_signature": False}, algorithms=["RS256"])

        # Extract relevant fields
        user_email = decoded_token.get("email", "")
        user_phone = decoded_token.get("phone_number", "")
        user_name = decoded_token.get("display_name", "")

        print(f"{Fore.CYAN}Extracted from token -> Email: {user_email}, Phone: {user_phone}, Name: {user_name}")

        return user_email, user_phone, user_name
    except ExpiredSignatureError:
        print(f"{Fore.RED}Token has expired.")
    except DecodeError:
        print(f"{Fore.RED}Failed to decode auth token.")
    except Exception as e:
        print(f"{Fore.RED}Unexpected error: {e}")

    return None, None, None           

def fetch_trip_details(from_city, to_city, date_of_journey, seat_class, train_number):
    url = "https://railspaapi.shohoz.com/v1.0/app/bookings/search-trips-v2"
    payload = {
        "from_city": from_city,
        "to_city": to_city,
        "date_of_journey": date_of_journey,
        "seat_class": seat_class
    }

    print(f"{Fore.YELLOW}Fetching trip details for {from_city} to {to_city} on {date_of_journey}...")

    while True:
        try:
            response = requests.get(url, headers=headers, params=payload)

            if response.status_code == 200:
                data = response.json().get("data", {}).get("trains", [])
                
                if not data:
                    print(f"{Fore.YELLOW}Trip details not available yet. Retrying in 1 second...")
                    time.sleep(1)
                    continue  # Retry if no trips are available

                for train in data:
                    if train.get('train_model') == str(train_number):  # Match train model with train_number
                        for seat in train.get('seat_types', []):
                            if seat.get('type') == seat_class:
                                trip_id = seat.get('trip_id')
                                trip_route_id = seat.get('trip_route_id')
                                boarding_point_id = train.get('boarding_points', [{}])[0].get('trip_point_id', None)
                                train_name = train.get('trip_number')
                                
                                print(f"{Fore.GREEN}Trip details found! Train: {train_name}, Trip ID: {trip_id}, Route ID: {trip_route_id}, Boarding Point ID: {boarding_point_id}")
                                return trip_id, trip_route_id, boarding_point_id, train_name

                print(f"{Fore.YELLOW}Train number {train_number} with seat class {seat_class} not available yet. Retrying in 1 second...")
                time.sleep(1)  # Retry every 1 second

            elif response.status_code in [500, 502, 503, 504]:
                print(f"{Fore.YELLOW}Server overloaded (HTTP {response.status_code}). Retrying in 1 second...")
                time.sleep(1)  # Retry after 1 second

            else:
                print(f"{Fore.RED}Failed to fetch trip details. HTTP Status: {response.status_code}")
                print(f"{Fore.CYAN}Server response: {response.text}")
                time.sleep(1)  # Retry after a delay on other errors

        except requests.RequestException as e:
                        print(f"{Fore.RED}Error during trip details fetch: {e}")
                        time.sleep(1)  # Retry after 1 second in case of an error

async def is_booking_available():
    url = "https://railspaapi.shohoz.com/v1.0/app/bookings/seat-layout"
    payload = {
        "trip_id": trip_id,
        "trip_route_id": trip_route_id
    }

    MIN_LOOP_INTERVAL = 0.001  # in seconds (1 ms), to avoid spamming too fast
    connector = aiohttp.TCPConnector(limit=20)  # Keep-Alive for better performance

    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            start_time = time.perf_counter()
            try:
                # Create a custom SSL context to disable certificate verification
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                async with session.get(url, headers=headers, json=payload, ssl=ssl_context) as response:
                    end_time = time.perf_counter()
                    elapsed = end_time - start_time
                    
                    if response.status == 200:
                        data = await response.json()
                        

                        # If seatLayout is available, return immediately
                        if "seatLayout" in data.get("data", ()):
                            print(f"{Fore.GREEN}Booking is now available!")
                            return data["data"]["seatLayout"]

                    elif response.status in [500, 502, 503, 504]:
                        print(f"{Fore.YELLOW}Server overloaded (HTTP {response.status}). Retrying...")
                    elif response.status == 422:
                        # NEW CODE: Process error details for 422 response
                        error_data = await response.json()
                        error_messages = error_data.get("error", {}).get("messages")
                        error_message = ""
                        error_key = ""

                        if isinstance(error_messages, list):
                            error_message = error_messages[0]
                        elif isinstance(error_messages, dict):
                            error_message = error_messages.get("message", "")
                            error_key = error_messages.get("errorKey", "")
                        else:
                            error_message = "Unknown error."

                        # Print the server response
                        print(f"{Fore.CY}Server response: {error_data}")

                        # Retry ONLY if the message contains "ticket purchase for this trip will be available"
                        if "ticket purchase for this trip will be available" in error_message:
                            print(f"{Fore.YELLOW}Booking is not open yet: {error_message}. Retrying until available...")
                            await asyncio.sleep(MIN_LOOP_INTERVAL)  # Retry after 1 ms
                            continue  # Go back to the loop

                        # If errorKey indicates OrderLimitExceeded, show a short message.
                        if error_key == "OrderLimitExceeded":
                            print(f"{Fore.RED}Error: You have reached the maximum ticket booking limit for {from_city} to {to_city} on {date_of_journey} for {train_name}. Please try booking again on a different day, or consider changing the train number, origin station, or destination.")
                        else:
                            # For other messages like ongoing purchase process or multiple order attempts,
                            # attempt to extract the wait time from the message and calculate the retry time.
                            time_match = re.search(r'(\d+)\s*minute[s]?\s*(\d+)\s*second[s]?', error_message, re.IGNORECASE)
                            if time_match:
                                minutes = int(time_match.group(1))
                                seconds = int(time_match.group(2))
                                total_seconds = minutes * 60 + seconds
                                current_time_formatted = time.strftime('%I:%M:%S %p', time.localtime())
                                future_time_formatted = time.strftime('%I:%M:%S %p', time.localtime(time.time() + total_seconds))
                                print(f"{Fore.RED}Error: {error_message} Current system time is {current_time_formatted}. Please try again after {future_time_formatted}.")
                            else:
                                print(f"{Fore.YELLOW}{error_message} Please try again later.")

                        # Stop further processing in these cases.
                        exit()
                    else:
                        # Some other status code
                        print(f"{Fore.RED}Failed to fetch seat layout. HTTP Status: {response.status}")
                        text_resp = await response.text()
                        print(f"{Fore.CYAN}Server response: {text_resp}")
            
            except aiohttp.clientError as e:
                end_time = time.perf.counter()
                elapsed = end_time - start_time
                print(f"{Fore.RED}An error occurred while checking booking availability: (e)")

            # Enforce a 1 ms minimum gap between loop starts
            if elapsed < MIN_LOOP_INTERVAL:
                await asyncio.sleep(MIN_LOOP_INTERVAL - elapsed)

def get_ticket_ids_from_layout(seat_layout, desired_seats, max_selectable_seat):
    selected_seat_details = {}

    # Case 1: If desired_seats is provided (at least one seat)
    if desired_seats:
        # Step 1: Select user-defined desired seats first, ensuring they are available
        for coach in seat_layout:
            for row in coach['layout']:
                for seat in row:
                    if seat['seat_availability'] == 1 and seat['seat_number'] in desired_seats:
                        selected_seat_details[seat['ticket_id']] = seat['seat_number']
                        if len(selected_seat_details) == max_selectable_seat:
                            return selected_seat_details

        # Step 2: Fill the remaining seats by checking nearby available ones
        for coach in seat_layout:
            for row in coach['layout']:
                seat_numbers = [seat for seat in row if seat['seat_availability'] == 1]

                for desired_seat in desired_seats:
                    nearby_seats = [s for s in seat_numbers if s['seat_number'] == desired_seat]

                    if nearby_seats:
                        desired_index = seat_numbers.index(nearby_seats[0])  
                        
                        # Check forward and backward for nearest available seats
                        for offset in range(1, len(seat_numbers)):
                            # Look forward
                            if desired_index + offset < len(seat_numbers):
                                seat = seat_numbers[desired_index + offset]
                                if seat['seat_availability'] == 1 and seat['seat_number'] not in selected_seat_details.values():
                                    selected_seat_details[seat['ticket_id']] = seat['seat_number']
                                    if len(selected_seat_details) == max_selectable_seat:
                                        return selected_seat_details

                            # Look backward
                            if desired_index - offset >= 0:
                                seat = seat_numbers[desired_index - offset]
                                if seat['seat_availability'] == 1 and seat['seat_number'] not in selected_seat_details.values():
                                    selected_seat_details[seat['ticket_id']] = seat['seat_number']
                                    if len(selected_seat_details) == max_selectable_seat:
                                        return selected_seat_details

        # Step 3: If not enough seats found, fill remaining seats arbitrarily
        for coach in seat_layout:
            for row in coach['layout']:
                for seat in row:
                    if seat['seat_availability'] == 1 and seat['seat_number'] not in selected_seat_details.values():
                        selected_seat_details[seat['ticket_id']] = seat['seat_number']
                        if len(selected_seat_details) == max_selectable_seat:
                            return selected_seat_details

    else:
        # Case 2: When desired_seats is empty, apply the new seat selection algorithm

        selected_seats = []

        # Step 1: Process seat layout and filter available seats by coach
        all_available_seats = [] 
            
        for layout in seat_layout:
            coach_name = layout['floor_name']
            seats = [seat for row in layout['layout'] for seat in row if seat['seat_availability'] == 1]

            if seats:
                seats.sort(key=lambda x: int(x['seat_number'].split('-')[-1])) # Sort numerically
                all_available_seats.append({'coach': coach_name, 'seats': seats})

        # Step 2: Look for contiguous seats in the same coach from the middle
        for coach_data in all_available_seats:
            coach_name = coach_data['coach']
            seats = coach_data['seats']
                
            mid_index = len(seats) // 2
            for i in range(max(0, mid_index - max_selectable_seat), min(mid_index + 1, len(seats) - max_selectable_seat + 1)):
                block = seats[i:i + max_selectable_seat]
                seat_numbers = [int(seat['seat_number'].split('-')[-1]) for seat in block]

                if max(seat_numbers) - min(seat_numbers) == max_selectable_seat - 1:
                    for seat in block:
                        selected_seat_details[seat['ticket_id']] = seat['seat_number']
                    return selected_seat_details

        # Step 3: Symmetric pairing around the middle (fallback strategy)
        for coach_data in all_available_seats:
            if len(selected_seats) >= max_selectable_seat:
                break

            coach_name = coach_data['coach']
            seats = coach_data['seats']
            coach_selected_seats = []
                
            mid_index = len(seats) // 2
            left = mid_index - 1
            right = mid_index

            while len(selected_seats) < max_selectable_seat and (left >= 0 or right < len(seats)):
                if left >= 0 and len(selected_seats) < max_selectable_seat:
                    coach_selected_seats.append(seats[left])
                    selected_seats.append(seats[left])
                    left -= 1
                        
                if right < len(seats) and len(selected_seats) < max_selectable_seat:
                    coach_selected_seats.append(seats[right])
                    selected_seats.append(seats[right])
                    right += 1
                        
            if coach_selected_seats:
                for seat in coach_selected_seats:
                    selected_seat_details[seat['ticket_id']] = seat['seat_number']
                if len(selected_seat_details) == max_selectable_seat:
                    return selected_seat_details

        # Step 4: Multi-coach fallback if necessary
        if len(selected_seats) < max_selectable_seat:
            for coach_data in all_available_seats:
                if len(selected_seats) >= max_selectable_seat:
                    break

                coach_name = coach_data['coach']
                seats = coach_data['seats']
                
                for seat in seats:
                    if len(selected_seats) >= max_selectable_seat:
                        break
                    if seat not in selected_seat_details.values():
                        selected_seat_details[seat['ticket_id']] = seat['seat_number']
                        selected_seats.append(seat)
                        
    # Return the seats found even if they are fewer than max_selectable_seat
    if selected_seat_details:
        print(f"{Fore.YELLOW}Warning: Proceeding with {len(selected_seat_details)} seats instead of {max_selectable_seat}.")
        return selected_seat_details

    print(f"{Fore.RED}No seats available to proceed.")
    return None

# Handling multiple tickets for confirm payload
def prepare_confirm_payload(otp):
    user_email, user_phone, user_name = extract_user_info_from_token()

    # Prepare passenger details dynamically based on the number of tickets
    if len(ticket_ids) > 1:
        passenger_names = [user_name] # Start with the first user
        for i in range(1, len(ticket_ids)):
            passenger_name = input(f"{Fore.YELLOW}Enter passenger {i + 1} name: ")
            passenger_names.append(passenger_name)

        confirm_payload = {
            "is_bkash_online": True,
            "boarding_point_id": boarding_point_id,
            "from_city": from_city,
            "to_city": to_city,
            "date_of_journey": date_of_journey,
            "seat_class": seat_class,
            "passengerType": ["Adult"] * len(ticket_ids),
            "gender": ["male"] * len(ticket_ids),
            "pname": passenger_names,
            "pmobile": user_phone,
            "pemail": user_email,
            "trip_id": trip_id,
            "trip_route_id": trip_route_id,
            "ticket_ids": ticket_ids,
            "contactperson": 0,
            "otp": otp,
            "selected_mobile_transaction": 1
        }     
    else:
        confirm_payload = {
            "is_bkash_online": True,
            "boarding_point_id": boarding_point_id,
            "from_city": from_city,
            "to_city": to_city,
            "date_of_journey": date_of_journey,
            "seat_class": seat_class,
            "passengerType": ["Adult"],
            "gender": ["male"],
            "pname": [user_name],
            "pmobile": user_phone,
            "pemail": user_email,
            "trip_id": trip_id,
            "trip_route_id": trip_route_id,
            "ticket_ids": ticket_ids,
            "contactperson": 8,
            "otp": otp,
            "selected_mobile_transaction": 1
        }
        
    return confirm_payload

# Stop 1: Reserve Seats for all ticket IDs concurrently
def reserve_seat():
    global ticket_ids  # Declare global before using the variable
    
    print(f"{Fore.YELLOW}Waiting for seat layout availability...")
    
    # Check for seat layout availability
    seat_layout = asyncio.run(is_booking_available())
    if not seat_layout:
        print(f"{Fore.RED}Seat layout could not be retrieved. Exiting.")
        return False
    
    ticket_id_map = get_ticket_ids_from_layout(seat_layout, desired_seats, max_selectable_seat)
    
    if not ticket_id_map:
        print(f"{Fore.RED}No matching seats found based on desired preferences. Exiting.")
        return False
    
    # Prepare ticket_ids list and seat mapping for display
    ticket_ids = list(ticket_id_map.keys())
    print(f"{Fore.GREEN}Seats matched! Details: {', '.join([f'{ticket_id_map[ticket]} (Ticket_ID: {ticket})' for ticket in ticket_ids])}")               
                                        
    successful_ticket_ids = []
    stop_reservation_due_to_limit = False

    def reserve_single_seat(ticket):
        nonlocal stop_reservation_due_to_limit
        if stop_reservation_due_to_limit:
            return False  # Stop further reservation attempts if limit error occurred

        url = "https://railspaapi.shohoz.com/v1.0/app/bookings/reserve-seat"
        payload = {
            "ticket_id": ticket,
            "route_id": trip_route_id
        }

        while True:
            try:
                response = requests.patch(url, headers=headers, json=payload)
                print(f"{Fore.CYAN}Response from Reserve Seat API for Seat {ticket_id_map[ticket]} (Ticket ID: {ticket}): {response.text}")

                if response.status_code == 200:
                    data = response.json()
                    if data["data"].get("ack") == 1:  # Success is indicated by "ack": 1
                        print(f"{Fore.GREEN}Seat {ticket_id_map[ticket]} (Ticket ID: {ticket}) reserved successfully!")
                        successful_ticket_ids.append(ticket)
                        return True
                    else:
                        print(f"{Fore.RED}Failed to reserve seat {ticket_id_map[ticket]} (Ticket ID: {ticket}): {data}")
                        return False

                elif response.status_code == 422:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("messages", {}).get("error_msg", "")
                    if "Maximum 4 seats can be booked at a time" in error_msg:
                        print(f"{Fore.RED}Error: {error_msg}. Stopping further seat reservation.")
                        stop_reservation_due_to_limit = True
                        return False  # Stop attempting further reservations
                    elif "Sorry! this ticket is not available now." in error_msg:
                        print(f"{Fore.RED}Seat {ticket_id_map[ticket]} (Ticket ID: {ticket}) is not available now. Skipping retry.")
                        return False

                elif response.status_code in [500, 502, 503, 504]:
                    print(f"{Fore.YELLOW}Server overloaded (HTTP {response.status_code}). Retrying in 100 milliseconds...")
                    time.sleep(0.1)  # Retry after 100 milliseconds
            
                else:
                    print(f"{Fore.RED}Error: {response.status_code} - {response.text}")
                    return False
            
            except Exception as e:
                print(f"{Fore.RED}Exception occurred while reserving seat {ticket_id_map[ticket]} (Ticket ID: {ticket}): {e}")
                time.sleep(0.1)  # Retry after 100 milliseconds in case of an exception

    print(f"{Fore.YELLOW}Initiating seat reservation process for {len(ticket_ids)} tickets...")

    with ThreadPoolExecutor(max_workers=len(ticket_ids)) as executor:
        executor.map(reserve_single_seat, ticket_ids)

    if successful_ticket_ids:
        ticket_ids = successful_ticket_ids  # Update with successful ones
        print(f"{Fore.GREEN}Successfully reserved tickets: {ticket_ids}. Proceeding to next step...")
        return True
    else:
        print(f"{Fore.RED}No seats could be reserved. Please try again.")
        return False

# Step 2: Send Passenger Details and Get OTP
def send_passenger_details():
    url = "https://railspaapi.shohoz.com/v1.0/app/bookings/passenger-details"
    payload = {
        "trip_id": trip_id,
        "trip_route_id": trip_route_id,
        "ticket_ids": ticket_ids
    }
    
    while True:
        try:
            response = requests.post(url, headers=headers, json=payload)
            print(f"{Fore.CYAN}Response from Passenger Details API: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if data["data"]["success"]:
                    print(f"{Fore.GREEN}OIP sent successfully!")
                    return True
                else:
                    print(f"{Fore.RED}Failed to send OIP: {data}]")
                    return False

            elif response.status_code in [500, 502, 503, 504]:
                print(f"{Fore.YELLOW}Server overloaded (HTTP {response.status_code}). Retrying in 1 second...")
                time.sleep(1) # Retry after 1 second

            else:
                print(f"{Fore.RED}Error: {response.status_code} - {response.text}]")
                return False

        except requests.RequestException as e:
            print(f"{Fore.RED}Exception occurred while sending passenger details: {e}]")
            time.sleep(1) # Retry after 1 second in case of an exception

# Step 3: Verify OIP and Confirm Booking
def verify_and_confirm_booking(otp):
    
    # Step 3.1: Verify OIP
    verify_url = "https://railspaapi.shohoz.com/v1.0/app/bookings/verify-otp"
    verify_payload = {
        "trip_id": trip_id,
        "trip_route_id": trip_route_id,
        "ticket_ids": ticket_ids,
        "otp": otp
    }
    
    try:
        while True:
            response = requests.post(verify_url, headers=headers, json=verify_payload)
            print(f"{Fore.CYAN}Response from OTP Verification API: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if not data["data"]["success"]:
                    print(f"{Fore.RED}Failed to verify OTP: {data}")
                    return False
                print(f"{Fore.GREEN}OTP verified successfully!")
                break
            
            elif response.status_code in [500, 502, 503, 504]:
                print(f"{Fore.YELLOW}Server overloaded (HTTP {response.status_code}). Retrying in 1 second...")
                time.sleep(1)
                
            elif response.status_code == 422:
                data = response.json()
                error_message = data.get("error", ()).get("message", ()).get("message", "Unknown error")
                error_key = data.get("error", ()).get("message", ()).get("errorKey", "Unknown errorkey")
                print(f"{Fore.RED}Error: {error_message} (ErrorKey: {error_key})")

                if error_key == "OtpNotVerified":
                    otp = input(f"{Fore.YELLOW}The OTP does not match. Please enter the correct OTP: ")
                    verify_payload["otp"] = otp
                else:
                    return False
                
            else:
                print(f"{Fore.RED}Error: {response.status_code} - {response.text}")
                return False
            
    except Exception as e:
        print(f"{Fore.RED}Exception occurred: {e}")
        time.sleep(1)
        return False

    # Step 3.2: Confirm Booking
    confirm_url = "https://railspaapi.shohoz.com/v1.0/app/bookings/confirm"

    confirm_payload = prepare_confirm_payload(otp)
    print(confirm_payload)

    # Payment method selection prompt
    print(f"\n{Fore.CYAN}Select Payment Method:")
    print("1. bKash\n2. Nagad\n3. Rocket\n4. Upay\n5. VISA\n6. Mastercard\n7. DBBL Nexus")

    while True:
        payment_choice = input(f"{Fore.YELLOW}Enter the number corresponding to your payment method: ")
        
        if payment_choice == '1': # bkash (default)
            print(f"{Fore.GREEN}Payment Method Selected: bkash")
            break

        elif payment_choice == '2': # Nagad
            confirm_payload["is_bkash_online"] = False
            confirm_payload["selected_mobile_transaction"] = 3
            print(f"{Fore.GREEN}Payment Method Selected: Nagad")
            break

        elif payment_choice == '3': # Rocket
            confirm_payload["is_bkash_online"] = False
            confirm_payload["selected_mobile_transaction"] = 4
            print(f"{Fore.GREEN}Payment Method Selected: Rocket")
            break

        elif payment_choice == '4': # Upay
            confirm_payload["is_bkash_online"] = False
            confirm_payload["selected_mobile_transaction"] = 5
            print(f"{Fore.GREEN}Payment Method Selected: Upay")
            break  
              
        elif payment_choice == '5': # VISA
            confirm_payload["is_bkash_online"] = False
            confirm_payload.pop("selected_mobile_transaction", None)
            confirm_payload["pg"] = "visa"
            print(f"{Fore.GREEN}Payment Method Selected: VISA")
            break

        elif payment_choice == '6': # Mastercard
            confirm_payload["is_bkash_online"] = False
            confirm_payload.pop("selected_mobile_transaction", None)
            confirm_payload["pg"] = "mastercard"
            print(f"{Fore.GREEN}Payment Method Selected: Mastercard")
            break

        elif payment_choice == '7': # DBBL Nexus
            confirm_payload["is_bkash_online"] = False
            confirm_payload.pop("selected_mobile_transaction", None)
            confirm_payload["pg"] = "nexus"
            print(f"{Fore.GREEN}Payment Method Selected: DBBL Nexus")
            break
        
        else:
            print(f"{Fore.RED}Invalid selection! Please enter a number between 1 and 7.")

    while True:
        try:
            response = requests.patch(confirm_url, headers=headers, json=confirm_payload)
            print(f"{Fore.CYAN}Response from Confirm Booking API: {response.text}")

            if response.status_code == 200:
                data = response.json()
                if "redirectUrl" in data["data"]:
                    redirect_url = data["data"]["redirectUrl"]
                    print(f"\n{Fore.GREEN}{'='*50}")
                    print(f"{Fore.GREEN}Booking confirmed successfully!")
                    print(f"{Fore.YELLOW}IMPORTANT: Please note that this payment link can be used ONLY ONCE.")
                    print(f"{Fore.BLUE}Payment URL: {redirect_url}")
                    print(f"{Fore.GREEN}{'='*50}\n")
                    return True # Ensure successful return
                else:
                    print(f"{Fore.RED}Failed to confirm booking: {data}")
                    return False
                    
            elif response.status_code in [508, 502, 503, 504]:
                print(f"{Fore.YELLOW}Server overloaded (HTTP {response.status_code}). Retrying in 1 second...")
                time.sleep(1)
                    
            else:
                print(f"{Fore.RED}Error: {response.status_code} - {response.text}")
                return False
            
        except requests.RequestException as e:
            print(f"{Fore.RED}Exception occurred while confirming booking: {e}")
            time.sleep(1)
            return False

# Main Execution Flow
try:
    print(f"{Fore.CYAN}Starting ticket booking process...")

    # Step 1: Authenticate user and fetch authorization token
    auth_key = fetch_auth_token(mobile_number, password)
    
    # Update headers with the new token
    if auth_key:
        headers = {'Authorization': f'Bearer {auth_key}'}
    else:
        print(f"{Fore.RED}Failed to fetch auth token. Exiting...")
        exit()
        
    # Step 2: Retrieve trip details for the selected journey
    trip_id, trip_route_id, boarding_point_id, train_name = fetch_trip_details(from_city, to_city, date_of_journey, seat_class, train_number)

    # Ensure the retrieved trip details are valid
    if not trip_id or not trip_route_id or not boarding_point_id:
        print(f"{Fore.RED}Error: Could not fetch trip details. Please check your inputs.")
        exit()

    # Step 3: Attempt to reserve selected seats
    if reserve_seat():
        # Step 4: Send passenger details and request OTP for confirmation
        if send_passenger_details():
            print(f"{Fore.CYAN}Proceeding to OTP verification and confirmation...")

            # Step 5: Verify OTP and confirm the booking
            otp = input(f"{Fore.YELLOW}Enter the OTP received: ")
            if verify_and_confirm_booking(otp):
                print(f"{Fore.GREEN}Booking process completed successfully!")
            else:
                print(f"{Fore.RED}Failed to complete booking process.")
        else:
            print(f"{Fore.RED}Failed to send passenger details and get OTP.")
    else:
        print(f"{Fore.RED}Failed to reserve the seat.")
except Exception as e:
    print(f"{Fore.RED}An unexpected error occurred: {e}")
        
