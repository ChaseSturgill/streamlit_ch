import streamlit as st
import pandas as pd
import requests
import json
from datetime import date, timedelta, datetime
import numpy as np

# title of page
st.title("Cloud Optimization Analyses")

# ask user to input their CH API key
label_auth = "Enter your CloudHealth API key."
auth_id = st.text_input(
    label_auth,
    value="",
    max_chars=None,
    key=None,
    type="default",
    help=None,
    autocomplete=None,
    on_change=None,
    args=None,
    kwargs=None,
)

# ask user to input the client_id of ther customer they're interested in
label_client = "Enter the client ID."
client_id = st.text_input(
    label_client,
    value="",
    max_chars=None,
    key=None,
    type="default",
    help=None,
    autocomplete=None,
    on_change=None,
    args=None,
    kwargs=None,
)

if st.button("Calculate"):
    # generate header to use for API calls
    my_headers = {"Authorization": "Bearer " + auth_id}

    try:
        test_response = requests.get(
            "https://chapi.cloudhealthtech.com/olap_reports/cost/history?&api_version=2&client_api_id="
            + client_id
            + "&dimensions[]=time&dimensions[]=AWS-Service-Category&measure[]=cost&interval=monthly",
            headers=my_headers,
        )
        test_response.raise_for_status()
    except:
        st.text("Please enter a valid API token and customer ID.")

    # Hit the snapshot API first to grab customer information
    snapshot_response = requests.get(
        "https://chapi.cloudhealthtech.com/api/search?&api_version=2&client_api_id="
        + client_id
        + "&name=AwsSnapshot&query=is_active=1&fields=name,size,create_date,account.name",
        headers=my_headers,
    )

    # converts JSON to a list of dictionaries with the information of every active snapshots
    snapshots = json.loads(snapshot_response.text)

    # obtain customer name
    customer = snapshots[0]["account"]["name"].split("-")[0].strip()

    ################## Quarterly Increases ##########################
    quarter_response = requests.get(
        "https://chapi.cloudhealthtech.com/olap_reports/cost/history?&api_version=2&client_api_id="
        + client_id
        + "&dimensions[]=time&dimensions[]=AWS-Service-Category&measure[]=cost&interval=monthly&filters[]=time:select:-2,-3,-4",
        headers=my_headers,
    )

    # converts JSON to a list of dictionaries, initialize nested list to hold service items and past three months of data
    service_items = json.loads(quarter_response.text)
    qdata = [[], [], [], []]

    # get previous three month labels
    lastMonth = date.today().replace(day=1) - timedelta(days=1)
    twoMonths = lastMonth.replace(day=1) - timedelta(days=1)
    threeMonths = twoMonths.replace(day=1) - timedelta(days=1)

    # initalize labels for data
    qlabels = [
        "Service Items",
        threeMonths.strftime("%m-%Y"),
        twoMonths.strftime("%m-%Y"),
        lastMonth.strftime("%m-%Y"),
    ]

    # fill in data with service items, note that this pulls Direct listings (i.e. EC2 direct is the sum of all associated EC2 charges),
    # could remove with parent: -1 with exceptions for services with no children (workspace)
    iterate = 0
    for item in service_items["dimensions"][1]["AWS-Service-Category"]:
        qdata[0].append(item["label"])
        iterate += 1

    # fill in data with costs from past three months
    for i in range(10, 13):
        for item in service_items["data"][i]:
            qdata[i - 9].append(item[0])

    # convert nested list data into a dictionary and then into a dataframe
    qdictionary = dict(zip(qlabels, qdata))
    df = pd.DataFrame(data=qdictionary)

    # create column with % change from previous month and the month before
    df["Monthly % Change"] = (
        (df[lastMonth.strftime("%m-%Y")] - df[twoMonths.strftime("%m-%Y")])
        / df[twoMonths.strftime("%m-%Y")]
    ) * 100

    # export dataframe to streamlit
    st.header(customer)
    st.subheader("Costs from Past Three Months")
    st.dataframe(df)

    ################## EC2 On-Demand NFUs ##########################
    ec2_response = requests.get(
        "https://chapi.cloudhealthtech.com/olap_reports/usage/instance?&api_version=2&query=is_active=1&client_api_id="
        + client_id
        + "&dimensions[]=time&dimensions[]=AWS-Coverage-Type&measures[]=nf_instances&interval=monthly&filters[]=time:select:-2, -3, -4",
        headers=my_headers,
    )

    # Converts JSON to a list of dictionaries, initialize nested list to NFUs by coverage type and their previous month's costs
    coverage = json.loads(ec2_response.text)
    ec2data = [[], [], []]
    categories = []

    # Get previous three month labels
    lastMonth = date.today().replace(day=1) - timedelta(days=1)
    twoMonths = lastMonth.replace(day=1) - timedelta(days=1)
    threeMonths = twoMonths.replace(day=1) - timedelta(days=1)

    # Initalize labels for data
    ec2labels = [
        threeMonths.strftime("%m-%Y"),
        twoMonths.strftime("%m-%Y"),
        lastMonth.strftime("%m-%Y"),
    ]

    # grab all buckets coverage types
    for item in coverage["dimensions"][1]["AWS-Coverage-Type"]:
        categories.append(item["label"])

    # Fill in data with costs from past three months
    for i in range(10, 13):
        for item in coverage["data"][i]:
            try:
                ec2data[i - 10].append(round(item[0], 2))
            except:
                ec2data[i - 10].append(0)

    # Convert nested list data into a dictionary and then into a dataframe
    ec2dictionary = dict(zip(ec2labels, ec2data))
    ec2df = pd.DataFrame(data=ec2dictionary, index=categories)

    # Creare new row showing on-demand % for each month
    odp = round(((ec2df.loc["On Demand"] / ec2df.loc["Total"]) * 100), 2)
    odpdf = (pd.DataFrame(data=odp)).transpose()
    odpdf["Monthly % Change"] = round(
        (
            (odpdf[lastMonth.strftime("%m-%Y")] - odpdf[twoMonths.strftime("%m-%Y")])
            / odpdf[twoMonths.strftime("%m-%Y")]
        )
        * 100,
        2,
    )

    # Create column with % change from previous month and the month before
    ec2df["Monthly % Change"] = round(
        (
            (ec2df[lastMonth.strftime("%m-%Y")] - ec2df[twoMonths.strftime("%m-%Y")])
            / ec2df[twoMonths.strftime("%m-%Y")]
        )
        * 100,
        2,
    )

    # export dataframe to streamlit
    st.subheader("EC2 NFU Coverage")
    st.dataframe(ec2df)
    st.subheader("EC2 On Demand Percentage by NFU")
    st.dataframe(odpdf)

    ################## S3 Bucket Info ##########################
    s3_response = requests.get(
        "https://chapi.cloudhealthtech.com/olap_reports/cost/s3?&api_version=2&client_api_id="
        + client_id
        + "&dimensions[]=time&dimensions[]=S3-Bucket&measure[]=s3_cost_storage&interval=monthly&filters[]=time:select:-1, -2, -3",
        headers=my_headers,
    )

    # converts JSON to a list of dictionaries, initialize nested list to s3 buckets and their previous month's costs
    buckets = json.loads(s3_response.text)
    s3data = [[], [], [], []]

    # finalize labels for data
    s3labels = [
        "Bucket",
        threeMonths.strftime("%m-%Y"),
        twoMonths.strftime("%m-%Y"),
        lastMonth.strftime("%m-%Y"),
    ]

    # store bucket names
    iterate = 0
    for item in buckets["dimensions"][1]["S3-Bucket"]:
        s3data[0].append(item["label"])
        iterate += 1

    # fill in data with costs from past three months
    for i in range(10, 13):
        for item in buckets["data"][i]:
            s3data[i - 9].append(item[0])

    # convert nested list data into a dictionary and then into a dataframe
    s3dictionary = dict(zip(s3labels, s3data))
    s3df_all = pd.DataFrame(data=s3dictionary)

    # create column with % change from previous month and the month before
    s3df_all["Monthly % Change"] = (
        (s3df_all[lastMonth.strftime("%m-%Y")] - s3df_all[twoMonths.strftime("%m-%Y")])
        / s3df_all[twoMonths.strftime("%m-%Y")]
    ) * 100

    # Filter out buckets with no costs last month
    s3df_all[lastMonth.strftime("%m-%Y")].replace("", np.nan, inplace=True)
    s3df = s3df_all.dropna(subset=[lastMonth.strftime("%m-%Y")])

    # compute total number of buckets incurring costs
    totalBuckets = len(s3df)

    # export dataframe to streamlit
    st.subheader("S3 Bucket Costs")
    st.text("Total number of buckets: " + str(totalBuckets))
    st.dataframe(s3df)

    ################## Snapshot Info ##########################
    # initialize counter for number of snapshots created before 2021
    before2021 = 0

    # create new key:value pair for the age of each snapshot based on today's date
    for snapshot in snapshots:
        snapshot["age"] = (
            date.today()
            - datetime.strptime(snapshot["create_date"], "%Y-%m-%dT%H:%M:%SZ").date()
        ).days
        if datetime.strptime(snapshot["create_date"], "%Y-%m-%dT%H:%M:%SZ").year < 2021:
            before2021 += 1

    # find total number of snapshots, average age of snapshots, and % created before 2021
    totalSnapshots = len(snapshots)
    averageAge = int(sum(snapshot["age"] for snapshot in snapshots) / totalSnapshots)
    percentBefore2021 = int((before2021 / totalSnapshots) * 100)

    # find oldest snapshot
    ageList = [snapshot["age"] for snapshot in snapshots]
    oldest = max(ageList)
    oldestIndex = ageList.index(oldest)
    oldestSnapshot = datetime.strptime(
        snapshots[oldestIndex]["create_date"], "%Y-%m-%dT%H:%M:%SZ"
    ).date()

    # find largest snapshot
    sizeList = [snapshot["size"] for snapshot in snapshots]
    largest = max(sizeList)

    # print analysis
    st.subheader("Snapshot Information")
    st.text(str(totalSnapshots) + " snapshots")
    st.text("Average Age: " + str(averageAge) + " days")
    st.text(
        str(percentBefore2021)
        + "% created before 2021 ("
        + str(before2021)
        + " snapshots)"
    )
    st.text("Oldest Snapshot: " + str(oldestSnapshot))
    st.text("Largest Snapshot: " + str(largest) + " GB")

    ################## GP2 Volume Savings ##########################
    volume_response = requests.get(
        "https://chapi.cloudhealthtech.com/api/search?&api_version=2&client_api_id="
        + client_id
        + "&name=AwsVolume&query=volume_type='gp2'+and+is_active=1&fields=volume_type,size,name,price_per_month,in_use,account.name",
        headers=my_headers,
    )

    # Converts JSON to a list of dictionaries with the information of every active volume
    volumes = json.loads(volume_response.text)

    # Initialize gp2 count and cost
    attached_gp2_volumes = 0
    cost_of_volumes = 0

    # Only count if volume is attached and sum monthly costs of attached volumes
    for volume in volumes:
        if volume["in_use"] and volume["size"] < 1000:
            attached_gp2_volumes += 1
            cost_of_volumes += float(volume["price_per_month"][1:].replace(",", ""))

    # Convert volume cost to savings (20% for gp2 to gp3 converion), print results
    savings = round(0.2 * cost_of_volumes, 2)

    # Find largest volume
    sizeList = [volume["size"] for volume in volumes]
    largest = max(sizeList) if len(sizeList) > 0 else 0

    # Print analysis
    st.subheader("GP2 Volume Information")
    st.text("Number of attached gp2 volumes under 1TB: " + str(attached_gp2_volumes))
    st.text("Monthly savings by converting to gp3: " + str(savings))
    st.text("Largest GP2 Volume: " + str(largest) + "GB")

    ################## Unattached Volume Savings ##########################
    uav_response = requests.get(
        "https://chapi.cloudhealthtech.com/api/search?&api_version=2&client_api_id="
        + client_id
        + "&name=AwsVolume&query=is_active=1&fields=volume_type,size,name,price_per_month,in_use,account.name",
        headers=my_headers,
    )

    # Converts JSON to a list of dictionaries with the information of every active volume
    uav_volumes = json.loads(uav_response.text)

    # Initialize gp2 count and cost
    unattached_volumes = 0
    uav_savings = 0

    # Only count if volume is attached and sum monthly costs of attached volumes
    for volume in uav_volumes:
        if not volume["in_use"]:
            unattached_volumes += 1
            uav_savings += float(volume["price_per_month"][1:].replace(",", ""))

    # Find largest unattached volume
    uav_sizeList = [volume["size"] for volume in uav_volumes if not volume["in_use"]]
    uav_largest = max(uav_sizeList) if len(uav_sizeList) > 0 else 0

    uav_savings = round(uav_savings, 2)
    # Print analysis
    st.subheader("Unattached Volume Information")
    st.text("Number of unattached volumes: " + str(unattached_volumes))
    st.text("Monthly savings by deleting volumes: " + str(uav_savings))
    st.text("Largest Unattached Volume: " + str(uav_largest) + "GB")
