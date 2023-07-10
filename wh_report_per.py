import datetime
import requests
import json
import pandas
from pytz import timezone
import io
import streamlit as st
import pydeck as pdk
import dateutil.parser
import tracemalloc

tracemalloc.start()

st.set_page_config(layout="wide")

CLAIM_SECRETS = st.secrets["CLAIM_SECRETS"]
CLIENT_LIST = st.secrets["CLIENTS"]
#SHEET_KEY = st.secrets["SHEET_KEY"]
#SHEET_ID = st.secrets["SHEET_ID"]
API_URL = st.secrets["API_URL"]
FILE_BUFFER = io.BytesIO()


def get_claims(secret, date_from, date_to, cursor=0):
    url = API_URL
    timezone_offset = "-05:00"
    payload = json.dumps({
        "created_from": f"{date_from}T00:00:00{timezone_offset}",
        "created_to": f"{date_to}T23:59:59{timezone_offset}",
        "limit": 1000,
        "cursor": cursor
    }) if cursor == 0 else json.dumps({"cursor": cursor})

    headers = {
        'Content-Type': 'application/json',
        'Accept-Language': 'en',
        'Authorization': f"Bearer {secret}"
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    claims = json.loads(response.text)
    cursor = None
    try:
        cursor = claims['cursor']
        print(f"CURSOR: {cursor}")
    except:
        print("LAST PAGE PROCESSED")
    try:
        return claims['claims'], cursor
    except:
        return [], None


def get_report(option="Today", start_=None, end_=None) -> pandas.DataFrame:
    
    offset_back = 0
    if option == "Yesterday":
        offset_back = 1
    elif option == "Tomorrow":
        offset_back = -1
    elif option == "Received":
        offset_back = 0
    
    client_timezone = "America/Lima"

    if option == "Monthly":
        start_ = "2023-06-01"
        end_ = "2023-07-31"
        today = datetime.datetime.now(timezone(client_timezone))
        date_from_offset = datetime.datetime.fromisoformat(start_).astimezone(
            timezone(client_timezone)) - datetime.timedelta(days=1)
        date_from = date_from_offset.strftime("%Y-%m-%d")
        date_to = end_
    elif option == "Weekly":
        start_date = datetime.datetime.now(timezone(client_timezone))-datetime.timedelta(days=datetime.datetime.weekday(datetime.datetime.now(timezone(client_timezone))))
        end_date=start_date + datetime.timedelta(days=6)
        start_ = start_date.strftime("%Y-%m-%d")
        end_ = end_date.strftime("%Y-%m-%d")
        #start_ = "2023-06-26"
        #end_ = "2023-07-02"
        today = datetime.datetime.now(timezone(client_timezone))
        date_from_offset = datetime.datetime.fromisoformat(start_).astimezone(
            timezone(client_timezone)) - datetime.timedelta(days=1)
        date_from = date_from_offset.strftime("%Y-%m-%d")
        date_to = end_
    elif option == "Received":
        today = datetime.datetime.now(timezone(client_timezone)) - datetime.timedelta(days=offset_back)
        search_from = today.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=7)
        search_to = today.replace(hour=23, minute=59, second=59, microsecond=999999) + datetime.timedelta(days=2)
        date_from = search_from.strftime("%Y-%m-%d")
        date_to = search_to.strftime("%Y-%m-%d")        
    else:
        today = datetime.datetime.now(timezone(client_timezone)) - datetime.timedelta(days=offset_back)
        search_from = today.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=2)
        search_to = today.replace(hour=23, minute=59, second=59, microsecond=999999)
        date_from = search_from.strftime("%Y-%m-%d")
        date_to = search_to.strftime("%Y-%m-%d")

    today = today.strftime("%Y-%m-%d")
    report = []
    i = 0
    for secret in CLAIM_SECRETS:
        claims, cursor = get_claims(secret, date_from, date_to)
        while cursor:
            new_page_claims, cursor = get_claims(secret, date_from, date_to, cursor)
            claims = claims + new_page_claims
        print(f"{datetime.datetime.now()}: Processing {len(claims)} claims")
        for claim in claims:
            try:
                claim_from_time = claim['same_day_data']['delivery_interval']['from']
            except:
                continue
            cutoff_time = datetime.datetime.fromisoformat(claim_from_time).astimezone(timezone(client_timezone))
            cutoff_date = cutoff_time.strftime("%Y-%m-%d")
            if not start_ and option != "Received":
                if cutoff_date != today:
                    continue
            report_cutoff = cutoff_time.strftime("%Y-%m-%d %H:%M")
            try:
                report_client_id = claim['route_points'][0]['external_order_id']
            except:
                report_client_id = "External ID not set"
            try:
                report_barcode = claim['route_points'][1]['external_order_id']
            except:
                report_barcode = "Barcode not set"
            report_claim_id = claim['id']
            try:
                report_lo_code = claim['items'][0]['extra_id']
            except:
                report_lo_code = "No LO code"
            report_client = CLIENT_LIST[i]
            report_pickup_address = claim['route_points'][0]['address']['fullname']
            report_pod_point_id = str(claim['route_points'][1]['id'])
            report_receiver_address = claim['route_points'][1]['address']['fullname']
            report_receiver_phone = claim['route_points'][1]['contact']['phone']
            report_receiver_name = claim['route_points'][1]['contact']['name']
            try:
                report_comment = claim['comment']
            except:
                report_comment = "Missing comment in claim"
            report_status = claim['status']
            report_created_time = dateutil.parser.isoparse(claim['created_ts']).astimezone(timezone(client_timezone))
            report_status_time = dateutil.parser.isoparse(claim['updated_ts']).astimezone(timezone(client_timezone))
            report_longitude = claim['route_points'][1]['address']['coordinates'][0]
            report_latitude = claim['route_points'][1]['address']['coordinates'][1]
            report_store_longitude = claim['route_points'][0]['address']['coordinates'][0]
            report_store_latitude = claim['route_points'][0]['address']['coordinates'][1]
            report_corp_id = claim['corp_client_id']
            try:
                report_courier_name = claim['performer_info']['courier_name']
                report_courier_park = claim['performer_info']['legal_name']
            except:
                report_courier_name = "No courier yet"
                report_courier_park = "No courier yet"
            try:
                report_return_reason = str(claim['route_points'][1]['return_reasons'])
#                report_return_comment = claim['route_points'][1]['return_comment']
            except:
                report_return_reason = "No return reasons"
#               report_return_comment = "No return comments"
            try:
                report_route_id = claim['route_id']
            except:
                report_route_id = "No route"
            try:
                report_point_B_time = datetime.datetime.strptime(claim['route_points'][1]['visited_at']['actual'],"%Y-%m-%dT%H:%M:%S.%f%z").astimezone(
        timezone(client_timezone))
                report_point_B_time = report_point_B_time.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
            except:
                report_point_B_time = "Point B was never visited"
            row = [report_cutoff, report_created_time, report_client, report_client_id, report_barcode, report_claim_id, report_lo_code, report_status, report_status_time, 
                   report_pod_point_id, report_pickup_address, report_receiver_address, report_receiver_phone, report_receiver_name, report_comment,
                   report_courier_name, report_courier_park,
                   report_return_reason, report_route_id,
                   report_longitude, report_latitude, report_store_longitude, report_store_latitude, report_corp_id, report_point_B_time]
            report.append(row)
        i = i + 1
    
    print(f"{datetime.datetime.now()}: Building dataframe")
    result_frame = pandas.DataFrame(report,
                                    columns=["cutoff", "created_time", "client", "client_id", "barcode", "claim_id", "lo_code", "status", "status_time",
                                             "pod_point_id", "pickup_address", "receiver_address", "receiver_phone", "receiver_name", "client_comment", 
                                             "courier_name", "courier_park",
                                             "return_reason", "route_id", "lon", "lat", "store_lon", "store_lat",
                                             "corp_client_id", "point_B_time"])
#     orders_with_pod = get_pod_orders()
#     result_frame = result_frame.apply(lambda row: check_for_pod(row, orders_with_pod), axis=1)
#    try:
#        result_frame.insert(3, 'proof', result_frame.pop('proof'))
#    except:
#        print("POD failed/ disabled")
    print(f"{datetime.datetime.now()}: Constructed dataframe")
    return result_frame


st.markdown(f"# Peru warehouse routes report")

if st.sidebar.button("Refresh data 🔮", type="primary"):
    st.cache_data.clear()
st.sidebar.caption(f"Page reload doesn't refresh the data.\nInstead, use this button to get a fresh report")

option = st.sidebar.selectbox(
    "Select report date:",
    ["Weekly", "Monthly", "Received", "Today", "Yesterday", "Tomorrow"]  # Disabled Monthly for now
)


@st.cache_data(ttl=1800.0)
def get_cached_report(option):
    report = get_report(option)
    return report


df = get_cached_report(option)        
delivered_today = len(df[df['status'].isin(['delivered', 'delivered_finish'])])

statuses = st.sidebar.multiselect(
    'Filter by status:',
    ['delivered',
     'pickuped',
     'returning',
     'cancelled_by_taxi',
     'delivery_arrived',
     'cancelled',
     'performer_lookup',
     'performer_found',
     'performer_draft',
     'returned_finish',
     'performer_not_found',
     'return_arrived',
     'delivered_finish',
     'failed',
     'accepted',
     'new',
     'pickup_arrived'])

print(f"{datetime.datetime.now()}: Get courier list for filters")
couriers = st.sidebar.multiselect(
    "Filter by courier:",
    df["courier_name"].unique()
)

without_cancelled = st.sidebar.checkbox("Without cancels")

print(f"{datetime.datetime.now()}: Filtering cancels")
if without_cancelled:
    df = df[~df["status"].isin(["cancelled", "performer_not_found", "failed", "cancelled_by_taxi"])]

print(f"{datetime.datetime.now()}: Displaying metrics")
if option != "Received":
    col1, col2, col3 = st.columns(3)
    col1.metric(f"Delivered {option.lower()} :package:", delivered_today)

print(f"{datetime.datetime.now()}: Applying status filters")
if not statuses or statuses == []:
    filtered_frame = df
else:
    filtered_frame = df[df['status'].isin(statuses)]

print(f"{datetime.datetime.now()}: Applying courier filters")
if couriers:
    filtered_frame = filtered_frame[filtered_frame['courier_name'].isin(couriers)]

if option == "Received":
    print("Filtering for only performer_lookup (received orders)")
    filtered_frame = filtered_frame[filtered_frame['status'].isin(["performer_lookup"])]

print(f"{datetime.datetime.now()}: Displaying dataframe")
st.dataframe(filtered_frame)

client_timezone = "America/Santiago"
TODAY = datetime.datetime.now(timezone(client_timezone)).strftime("%Y-%m-%d") \
    if option == "Today" \
    else datetime.datetime.now(timezone(client_timezone)) - datetime.timedelta(days=1)

stores_with_not_taken_routes = None
st.caption(
    f'Total of :blue[{len(filtered_frame)}] orders in the table.')

delivery_zone = [
          [
            [
              -71.51055812109378,
              -32.874119353472565
            ],
            [
              -70.98870753515628,
              -32.83702793369675
            ],
            [
              -70.81567286718752,
              -32.83702793369675
            ],
            [
              -70.58770655859377,
              -32.83702793369675
            ],
            [
              -70.42565821875002,
              -32.89034192619984
            ],
            [
              -70.33227442968752,
              -32.9135118294214
            ],
            [
              -70.28348928471766,
              -32.90431715470858
            ],
            [
              -70.23679739018641,
              -32.95759029024799
            ],
            [
              -70.22855764409265,
              -33.06172660923614
            ],
            [
              -70.2258110620614,
              -33.25578190832877
            ],
            [
              -70.2258110620614,
              -33.44249557763503
            ],
            [
              -70.2258110620614,
              -33.66785491230312
            ],
            [
              -70.28348928471766,
              -33.920101204217794
            ],
            [
              -70.2477837183114,
              -33.96130639558313
            ],
            [
              -70.2697563745614,
              -34.02993696840332
            ],
            [
              -70.29447561284265,
              -34.09622664563551
            ],
            [
              -70.42631155034265,
              -34.12135731262638
            ],
            [
              -70.72294240971765,
              -34.09165662407802
            ],
            [
              -71.0607719995614,
              -34.02536333784736
            ],
            [
              -71.68424612065515,
              -33.993340959083675
            ],
            [
              -71.8023491479989,
              -33.890329384665975
            ],
            [
              -71.78861623784266,
              -33.821585151962985
            ],
            [
              -71.64579397221765,
              -33.72065932438488
            ],
            [
              -71.61283498784265,
              -33.65407446323493
            ],
            [
              -71.5991020776864,
              -33.578242189039635
            ],
            [
              -71.58536916753016,
              -33.516147533925086
            ],
            [
              -71.63480764409265,
              -33.4816310487599
            ],
            [
              -71.68699270268641,
              -33.4148598051366
            ],
            [
              -71.6814995386239,
              -33.366475839464655
            ],
            [
              -71.63206106206141,
              -33.32728796352962
            ],
            [
              -71.65952688237392,
              -33.27654782395451
            ],
            [
              -71.66227346440517,
              -33.23501100976201
            ],
            [
              -71.68149953862391,
              -33.19345426960373
            ],
            [
              -71.68973928471766,
              -33.10565799303419
            ],
            [
              -71.64304739018641,
              -33.06172660927545
            ],
            [
              -71.58262258549892,
              -33.0501620377368
            ],
            [
              -71.52769094487392,
              -33.01545912458928
            ],
            [
              -71.52769094487392,
              -32.95527474050761
            ],
            [
              -71.51055812109378,
              -32.874119353472565
            ]
          ]
        ]

print(f"{datetime.datetime.now()}: Rendering map")
with st.expander(":round_pushpin: Orders on a map:"):
    st.caption(
        f'Hover order to see details. :green[Green] orders are delivered, and :red[red] – are the in delivery state. :orange[Orange] are returned or returning. Gray are cancelled.')
    chart_data_delivered = filtered_frame[filtered_frame["status"].isin(['delivered', 'delivered_finish'])]
    chart_data_in_delivery = filtered_frame[~filtered_frame["status"].isin(
        ['delivered', 'delivered_finish', 'cancelled', 'cancelled_by_taxi', 'returning', 'returned_finish',
         'return_arrived'])]
    chart_data_returns = filtered_frame[
        filtered_frame["status"].isin(['returning', 'returned_finish', 'return_arrived'])]
    chart_data_cancels = filtered_frame[filtered_frame["status"].isin(['cancelled', 'cancelled_by_taxi'])]
    view_state_lat = filtered_frame['lat'].iloc[0]
    view_state_lon = filtered_frame['lon'].iloc[0]
    
    st.pydeck_chart(pdk.Deck(
        map_style=None,
        height=1200,
        initial_view_state=pdk.ViewState(
            latitude=view_state_lat,
            longitude=view_state_lon,
            zoom=10,
            pitch=0,
        ),
        tooltip={"text": "{cutoff}\n{courier_name} : {status}\n{client_id} : {claim_id}"},
        layers=[
            pdk.Layer(
                'ScatterplotLayer',
                data=chart_data_delivered,
                get_position='[lon, lat]',
                get_color='[11, 102, 35, 160]',
                get_radius=200,
                pickable=True
            ),
            pdk.Layer(
                'ScatterplotLayer',
                data=chart_data_in_delivery,
                get_position='[lon, lat]',
                get_color='[200, 30, 0, 160]',
                get_radius=200,
                pickable=True
            ),
            pdk.Layer(
                'ScatterplotLayer',
                data=chart_data_cancels,
                get_position='[lon, lat]',
                get_color='[215, 210, 203, 200]',
                get_radius=200,
                pickable=True
            ),
            pdk.Layer(
                'ScatterplotLayer',
                data=chart_data_returns,
                get_position='[lon, lat]',
                get_color='[237, 139, 0, 160]',
                get_radius=200,
                pickable=True
            ),
            pdk.Layer(
                'ScatterplotLayer',
                data=filtered_frame,
                get_position=[-70.6945098, -33.3688048],
                get_color='[0, 128, 255, 160]',
                get_radius=250,
                pickable=True
            )
        ],
    ))


print(f"{datetime.datetime.now()}: Rendering download button")

with pandas.ExcelWriter(FILE_BUFFER, engine='xlsxwriter') as writer:
    filtered_frame["status_time"] = filtered_frame["status_time"].apply(lambda a: pandas.to_datetime(a).date()).reindex()
    filtered_frame["created_time"] = filtered_frame["created_time"].apply(lambda a: pandas.to_datetime(a).date()).reindex()
    filtered_frame.to_excel(writer, sheet_name='wh_routes_report')
    writer.close()

    st.download_button(
        label="Download report as xlsx",
        data=FILE_BUFFER,
        file_name=f"route_report_{TODAY}.xlsx",
        mime="application/vnd.ms-excel"
    )
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')
print("[ Top 20 ]")
for stat in top_stats[:20]:
    print(stat)

print(f"{datetime.datetime.now()}: Finished")
