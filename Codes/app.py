# -*- coding: utf-8 -*-

# visit http://127.0.0.1:8050/ in your web browser.

import dash
from dash import dcc
from dash import html
from dash import dash_table
import plotly.express as px
import pandas as pd
import camelot
from datetime import date
from datetime import timedelta
import requests
import bs4
import re

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

# Prepping base data
df = pd.read_csv("https://raw.githubusercontent.com/yixianc/sglocalcovidcases/main/data/Table%20of%20Daily%20Unlink%20Cases.csv")
df['Date'] = pd.to_datetime(df['Date'])

# Check and add in new data
# extract table from website
res = requests.get('https://www.moh.gov.sg/covid-19/testing/situation-report-pdf')
soup = bs4.BeautifulSoup(res.text, "html.parser")
table = soup.find(lambda tag: tag.name == 'table')
rows = table.findAll(lambda tag: tag.name == 'tr')

# extract the last date in table to check if there are new data to download
# extract first row that is not header
row1 = str(rows[1])
end = re.search(r'>(.*?)2021', row1).span(0)[1]
start = end - 11
lastdate = pd.to_datetime(row1[start:end])

ndaystoupdate = abs(lastdate - df['Date'].max()).days

warningmsg = ""

# there are new sitrep not added in consolidated table
if ndaystoupdate > 0:

    # extract all html links in website table
    alllinks = []
    for a in soup.find_all('a', href=True):
        alllinks.append(a['href'])

    # filter to only the libraries link
    libprefix = r'^/docs/librariesprovider5/'
    liblinks = []
    for i in alllinks:
        if re.search(libprefix, i) is not None:
            liblinks.append("https://www.moh.gov.sg" + re.search(libprefix, i).string)
    liblinkstoupdate = liblinks[:ndaystoupdate]
    liblinkstoupdate.reverse()  # reverse in order to extract numbers from oldest new sitrep

    # extract, calculate and append to consolidated table
    for nd in range(ndaystoupdate):
        newdate = df['Date'].max() + timedelta(days=1)

        # Additional check to see if PDF is uploaded correctly
        try:
            tempdate = re.search(r'(\d{8})', liblinkstoupdate[nd]).group()
            tempdate = pd.to_datetime(tempdate)
        except Exception:
            pass
        try:
            tempdate = re.search(r'(\d{2}-\w{3}-2021)', liblinkstoupdate[nd]).group()
            tempdate = pd.to_datetime(tempdate)
        except Exception:
            pass
        try:
            if tempdate != newdate:
                warningmsg = "Warning: PDF for " + str(newdate.date()) + " is uploaded wrongly! Expect " + str(newdate.date()) + " but PDF is for " + str(tempdate.date())
            else:
                pass
        except Exception:
            pass

        # update consolidated table
        newtable = camelot.read_pdf(liblinkstoupdate[nd], pages="1")

        # new wkly sum
        new7dlinkedqo = int(newtable[0].df[3][2])
        new7dlinkednotqo = int(newtable[0].df[3][3])
        new7dunlinked = int(newtable[0].df[3][4])

        # cal sum for past 6 days from consolidated table
        past6dlinkedqo = sum(df[-6:]["Linked and QO"])
        past6dlinkednotqo = sum(df[-6:]["Linked and not QO"])
        past6dunlinked = sum(df[-6:]["Unlinked"])

        newlinkedqo = new7dlinkedqo - past6dlinkedqo
        newlinkednotqo = new7dlinkednotqo - past6dlinkednotqo
        newunlinked = new7dunlinked - past6dunlinked

        newdaydf = pd.DataFrame({"Date": [newdate],
                                 "Linked and QO": [newlinkedqo],
                                 "Linked and not QO": [newlinkednotqo],
                                 "Unlinked": [newunlinked]})

        df = df.append(newdaydf)

# Convert data from wide to long
df_long = pd.melt(df, id_vars='Date', value_vars=['Linked and QO', 'Linked and not QO', 'Unlinked'], var_name="Type",
                  value_name="Num of Cases")

# Create another table showing Total Local Case Counts
Total = df.iloc[:, 1:].sum(axis=1)
df_tot = pd.DataFrame({"Date": df['Date'], "Total": Total})
# df_tot.set_index('Date',inplace=True)
# df_tot=df_tot.transpose()

fig = px.bar(df_long, x="Date", y="Num of Cases", text="Num of Cases",
             color="Type",
             color_discrete_map={
                 "Linked and QO": "green",
                 "Linked and not QO": "orange",
                 "Unlinked": "red"
             },
             title="Estimated Daily Number of Local Covid Cases (by Linked VS Unlinked)",
             category_orders={"Type": ['Unlinked', 'Linked and not QO', 'Linked and QO']},
             height=580
             )
fig.update_traces(textangle=90, selector=dict(type='bar'))
fig.update_layout(legend_traceorder="reversed")
fig.update_layout(legend_title_text="")
fig.update_layout(xaxis=dict(tickmode='linear'))

total_fig = px.line(df_tot, x="Date", y="Total", text="Total",
                    title="Estimated Daily Number of Local Covid Cases")
total_fig.update_layout(xaxis=dict(tickmode='linear'))
total_fig.update_traces(textposition="top center")

app.layout = html.Div(children=[
    html.H1(children='Daily Number of Local Covid Cases'),

    dcc.Markdown('''
     \n Estimated based on daily figures from [MOH Local Situation Report](https://www.moh.gov.sg/covid-19/testing/situation-report-pdf)
     \n Unlinked cases from 8 Sep are computed assuming there are no reclassification for cases in the previous days.
     \n *Data are unofficial estimates and are to be used at your own risk.*
     \n *Data for 12 Sep assumes the same proportion of linked qo, linked not on qo and unlinked as 11 Sep as MOH did not upload the correct sitrep for 12 Sep.*
     '''),

    html.Div(warningmsg),

    dcc.Graph(
        id='main-graph',
        figure=fig
    ),

    dcc.Graph(
        id='total-graph',
        figure=total_fig
    ),

    #    dash_table.DataTable(
    #        id='total-table',
    #        columns=[{"name": i, "id": i} for i in df_tot.columns],
    #        data=df_tot.to_dict('records')
    #    )

])

if __name__ == '__main__':
    app.run_server(debug=True)
