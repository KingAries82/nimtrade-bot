import discord
import requests
import asyncio
import configparser

from tabulate import tabulate
from bs4 import BeautifulSoup


conf = configparser.RawConfigParser()
conf.read("config.txt")

BOT_TOKEN = conf.get('goldenbot_conf', 'BOT_TOKEN')


def is_fiat(name):
    if name in ("USD", "EUR", "GBP", "AUD"):
        return True
    else:
        return False


def is_crypto(name):
    if name in ("GRLC", "BTC", "ETH", "LTC", "NANO"):
        return True
    else:
        return False


def get_rate_crypto(crypto, fiat="USD"):
    crypto_name = {"GRLC": "garlicoin",
                   "BTC": "bitcoin",
                   "ETH": "ethereum",
                   "LTC": "litecoin",
                   "NANO": "nano"}
    try:
        datas = requests.get("https://api.coinmarketcap.com/v1/ticker/{0}/?convert={1}".format(crypto_name[crypto], fiat), timeout=10)
    except requests.Timeout:
        return None

    datas = datas.json()[0]

    return float(datas["price_{}".format(fiat.lower())])


def get_fiats():
    try:
        usd_eur = requests.get("https://api.coinmarketcap.com/v1/ticker/garlicoin/?convert=EUR", timeout=10)
        gbp = requests.get("https://api.coinmarketcap.com/v1/ticker/garlicoin/?convert=GBP", timeout=10)
        aud = requests.get("https://api.coinmarketcap.com/v1/ticker/garlicoin/?convert=AUD", timeout=10)
    except requests.Timeout:
        return None

    usd_eur = usd_eur.json()[0]
    gbp = gbp.json()[0]
    aud = aud.json()[0]

    return float(usd_eur["price_usd"]), float(usd_eur["price_eur"]), float(gbp["price_gbp"]), float(aud["price_aud"])


def get_cryptos():
    try:
        grlc_btc = requests.get("https://api.coinmarketcap.com/v1/ticker/garlicoin/", timeout=10)
        eth_btc = requests.get("https://api.coinmarketcap.com/v1/ticker/ethereum/", timeout=10)
        ltc_btc = requests.get("https://api.coinmarketcap.com/v1/ticker/litecoin/", timeout=10)
        nano_btc = requests.get("https://api.coinmarketcap.com/v1/ticker/nano/", timeout=10)
    except requests.Timeout:
        return None

    grlc_btc = grlc_btc.json()[0]
    eth_btc = eth_btc.json()[0]
    ltc_btc = ltc_btc.json()[0]
    nano_btc = nano_btc.json()[0]

    grlc_btc = float(grlc_btc["price_btc"])
    grlc_eth = grlc_btc / float(eth_btc["price_btc"])
    grlc_ltc = grlc_btc / float(ltc_btc["price_btc"])
    grlc_nano = grlc_btc / float(nano_btc["price_btc"])

    return grlc_btc, grlc_eth, grlc_ltc, grlc_nano


def fstr(max_size, value):
    # Get the len of the integer part
    i_part = len(str(int(value)))
    f_part = max_size - i_part - 1

    formater = "{" + ":.{}f".format(f_part) + "}"

    return formater.format(value)


client = discord.Client()

@client.event
async def on_ready():
    print('Logged in as {} <@{}>'.format(client.user.name, client.user.id))
    print('------')

@client.event
async def on_message(message):
    if message.content.startswith("!fiat"):
        # Get the GRLC price in USD, EUR, GBP & AUD
        tmp = await client.send_message(message.channel, "Acquiring fiat rates from CoinMarketCap...")
        fiats = get_fiats()
        if fiats:
            await client.edit_message(tmp, "Acquiring fiat rates from CoinMarketCap... Done!")
            symbols = [("USD", "$"), ("EUR", "€"), ("GBP", "£"), ("AUD", "$")]
            data = [[symbols[i][0], "{0} {1}".format(symbols[i][1],fstr(9, fiats[i])), "₲ {}".format(fstr(9, 1/fiats[i]))] for i in range(4)]
            table = tabulate(data, headers=["", "Garlicoin", "Fiat"])

            await client.send_message(message.channel, "```{}```".format(table))
        else:
            # Timeout
            await client.edit_message(tmp, "Error : Couldn't reach CoinMarketCap (timeout)")

    if message.content.startswith("!crypto"):
        # Get the GRLC price in BTC, ETH, LTC, NANO
        tmp = await client.send_message(message.channel, "Acquiring crypto rates from CoinMarketCap...")
        cryptos = get_cryptos()

        if cryptos:
            await client.edit_message(tmp, "Acquiring crypto rates from CoinMarketCap... Done!")
            symbols = [("BTC", "฿"), ("ETH", "Ξ"), ("LTC", "Ł"), ("NANO", "η")]
            data = [[symbols[i][0], "{0} {1}".format(symbols[i][1],fstr(10, cryptos[i])), "₲ {}".format(fstr(10, 1/cryptos[i]))] for i in range(4)]
            table = tabulate(data, headers=["", "Garlicoin", "Crypto"])

            await client.send_message(message.channel, "```{}```".format(table))
        else:
            # Timeout
            await client.edit_message(tmp, "Error : Couldn't reach CoinMarketCap (timeout)")

    if message.content.startswith("!graph"):
        # TODO: Get details for Garlicoin (graph last 24h ?)
        pass

    if message.content.startswith("!conv"):
        # !conv [amount] [currency1] [currency2] [rate (optional)]
        # --> [currency1] [amount] = [currency2] [converted amount] ([rate])

        # Check if there is a rate
        msg = message.content.replace("!conv ", "").split(" ")
        if len(msg) == 3:
            # No rate given, get it from CoinMarketCap
            amount = float(msg[0].replace(",", ".")) # In case someone sends 10,2 GRLC instead of 10.2
            curr1 = msg[1]
            curr2 = msg[2]

            # FIAT -> CRYPTO, CRYPTO -> FIAT and CRYPTO -> CRYPTO are ok (FIAT -> FIAT is not)
            if is_fiat(curr1) and is_fiat(curr2):
                # Get the exchange rate (using BTC as a middle value)
                tmp = await client.send_message(message.channel, "Acquiring rates from CoinMarketCap...")
                fiat1_btc = get_rate_crypto("BTC", curr1)
                fiat2_btc = get_rate_crypto("BTC", curr2)

                if fiat1_btc and fiat2_btc:
                    await client.edit_message(tmp, "Acquiring rates from CoinMarketCap... Done!")
                    rate = fiat1_btc / fiat2_btc
                    conv_amount = amount * rate
                    await client.send_message(message.channel, "```{0} {1} = {2} {3:.6f} (rate: {4:.6f})```".format(curr1, msg[0], curr2, conv_amount, rate))
                else:
                    # Timeout
                    await client.edit_message(tmp, "Error : Couldn't reach CoinMarketCap (timeout)")

            elif is_crypto(curr1) and is_crypto(curr2):
                # Get each crypto rate in BTC then calculate the rate
                tmp = await client.send_message(message.channel, "Acquiring rates from CoinMarketCap...")
                crypto1_btc = get_rate_crypto(curr1, "BTC")
                crypto2_btc = get_rate_crypto(curr2, "BTC")

                if crypto1_btc and crypto2_btc:
                    await client.edit_message(tmp, "Acquiring rates from CoinMarketCap... Done!")
                    rate = crypto1_btc / crypto2_btc
                    conv_amount = amount * rate
                    await client.send_message(message.channel, "```{0} {1} = {2} {3:.6f} (rate: {4:.6f})```".format(curr1, msg[0], curr2, conv_amount, rate))
                else:
                    # Timeout
                    await client.edit_message(tmp, "Error : Couldn't reach CoinMarketCap (timeout)")

            elif is_crypto(curr1) or is_fiat(curr1) and is_crypto(curr2) or is_fiat(curr2):
                # Find the FIAT and ask CoinMarketCap for the crypto using the FIAT
                if is_crypto(curr1):
                    fiat = curr2
                    crypto = curr1
                else:
                    fiat = curr1
                    crypto = curr2

                tmp = await client.send_message(message.channel, "Acquiring rates from CoinMarketCap...")
                rate = get_rate_crypto(crypto, fiat)
                if rate:
                    await client.edit_message(tmp, "Acquiring rates from CoinMarketCap... Done!")
                    if fiat == curr1:
                        conv_amount = amount / rate
                        await client.send_message(message.channel, "```{0} {1} = {2} {3:.6f} (rate: {4:.6f})```".format(curr1, msg[0], curr2, conv_amount, 1/rate))
                    else:
                        conv_amount = amount * rate
                        await client.send_message(message.channel, "```{0} {1} = {2} {3:.6f} (rate: {4:.6f})```".format(curr1, msg[0], curr2, conv_amount, rate))

                else:
                    # Timeout
                    await client.edit_message(tmp, "Error : Couldn't reach CoinMarketCap (timeout)")

            else:
                # One or both currencies aren't known
                await client.send_message(message.channel, "One (or both) currency entered is not supported.")

        elif len(msg) == 4:
            # Make the calculation using the rate
            amount = float(msg[0].replace(",", ".")) # In case someone sends 10,2 GRLC instead of 10.2
            curr1 = msg[1]
            curr2 = msg[2]
            rate = float(msg[3].replace(",", ".")) # In case someone sends 0,02 instead of 0.02

            conv_amount = amount * rate
            await client.send_message(message.channel, "```{0} {1} = {2} {3:.6f} (rate: {4:.6f})```".format(curr1, msg[0], curr2, conv_amount, rate))

        else:
            # Not enough parameters sent
            await client.send_message(message.channel, "Not enough parameters given : `!conv [amount] [currency1] [currency2] [rate (optional)]`")

    if message.content.startswith("!exchange"):
        data = []
        tmp = await client.send_message(message.channel, "Acquiring exchange rates from CoinMarketCap...")
        try:
            ex = requests.get("https://coinmarketcap.com/currencies/garlicoin/#markets", timeout=10)
        except requests.Timeout:
            ex = None

        if ex:
            await client.edit_message(tmp, "Acquiring exchange rates from CoinMarketCap... Done!")
            soup = BeautifulSoup(ex.text, 'html.parser')
            table = soup.find('table', attrs={'id': 'markets-table'})
            table_body = table.find('tbody')

            rows = table_body.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                cols = [ele.text.strip() for ele in cols]
                data.append([ele for ele in cols if ele])

            data = [[x[0], x[1], x[2], x[3], x[4]] for x in data] # Remove columns
            table = tabulate(data, headers=["No", "Exchange", "Pair", "Volume", "Price"])
            await client.send_message(message.channel, "```{}```".format(table))
        else:
            # Timeout
            await client.edit_message(tmp, "Error : Couldn't reach CoinMarketCap (timeout)")

    # TODO: !help


client.run(BOT_TOKEN)
