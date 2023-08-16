

def frontpage_with_json(js,relays,time,uptime,deviceMac,ip):
    hour = time[4]
    minute = time[5]
    html = """
<!DOCTYPE html>
<html>
    <head> <title>Ohjausboksi</title> <meta http-equiv="refresh" content="900"></head>
    <style>
.styled-table {
    border-collapse: collapse;
    margin: 25px 0;
    margin-left: auto;
    margin-right: auto;
    font-size: 0.9em;
    font-family: sans-serif;
    width: 70%;
    min-width: 400px;
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
}
.styled-table caption {
    font-size: 1.5em;
    font-weight: bold;
    text-align: left;
    text-indent: 10px;
    line-height: 2.0;
}
.styled-table thead tr {
    background-color: #4DB6AC;
    color: #ffffff;
    text-align: center;
}
.styled-table th,
.styled-table td {
    padding: 12px 15px;
}
.styled-table tbody td {
    background-color: rgba(224, 242, 241, 0.4);
    text-align: center;
    font-size: 0.8em;
    border-left: 1px solid #4DB6AC;
    border-top: 1px solid #4DB6AC;
}
.styled-table tbody td:first-of-type {
    border-left: 0;
}
.styled-table tbody th {
    background-color: #4DB6AC;
    color: #ffffff;
    text-align: left;
    border-bottom: none;
}
    </style>"""
    
    html += """
    <body>
        <table class="styled-table" style="Width: 25% !important"><caption>System info</caption>
        <tbody>
            <tr><th scope="row">Device Mac</th><td style="border-top: none !important">{}</td></tr>
            <tr><th scope="row">Device IP</th><td>{}</td></tr>
            <tr><th scope="row">Uptime</th><td>{}</td></tr>
        </tbody></table>
        <table class="styled-table"><caption>Relay states at {:02d}.{:02d}</caption><thead>
            <tr>""".format(deviceMac,ip,uptime,time[4],time[5])
    channels = int(js['Metadata']['Channels'])           
    i = 0    
    while i < channels:
        html += "<th>Channel {}</th>".format(i + 1)
        i += 1
    html += "</tr></thead><tbody><tr>"
    i = 0    
    while i < channels:
        if relays[i].value() == 1:
            html += """<td style="background-color: #80CBC4 !important">ON</td>"""
        else:
            html += "<td>OFF</td>"
        i += 1
    html += """</tr></tbody></table>       
        <table class="styled-table"><caption>Schedules</caption><thead>
            <tr>
                <th></th>"""
    channels = int(js['Metadata']['Channels'])
    #hour = rtc.datetime()[4]
    for j in range(hour + 1, 24):
        html += "<th>{:02d}</th>".format(j)
    for j in range(hour - 1):
        html += "<th>{:02d}</th>".format(j)
            
    html += "</tr></thead><tbody>"   
    i = 0    
    while i < channels:
        html += "<tr><th scope={}>Channel {}</th>".format('"row"',i + 1)
        for j in range(hour + 1, 24):
            try:
                result = js['Channel{}'.format(i + 1)]['{}'.format(j)]
                if result == '1':
                    html += """<td style="background-color: #80CBC4 !important"></td>"""
                else:
                    html += "<td></td>"
            except:
                html += "<td>?</td>"
        for j in range(hour - 1):
            try:
                result = js['Channel{}'.format(i + 1)]['{}'.format(j)]
                if result == '1':
                    html += """<td style="background-color: #80CBC4 !important"></td>"""
                else:
                    html += "<td></td>"
            except:
                html += "<td>?</td>"
        html += "</tr>"
        i += 1
    html += """        
        </tbody></table>
    </body>
</html>
    """
    return html

def frontpage_without_json(time,uptime,deviceMac,ip):
    hour = time[4]
    minute = time[5]
    html = """
<!DOCTYPE html>
<html>
    <head> <title>Ohjausboksi</title> <meta http-equiv="refresh" content="900"></head>
    <style>
.styled-table {
    border-collapse: collapse;
    margin: 25px 0;
    margin-left: auto;
    margin-right: auto;
    font-size: 0.9em;
    font-family: sans-serif;
    width: 70%;
    min-width: 400px;
    box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
}
.styled-table caption {
    font-size: 1.5em;
    font-weight: bold;
    text-align: left;
    text-indent: 10px;
    line-height: 2.0;
}
.styled-table thead tr {
    background-color: #4DB6AC;
    color: #ffffff;
    text-align: center;
}
.styled-table th,
.styled-table td {
    padding: 12px 15px;
}
.styled-table tbody td {
    background-color: rgba(224, 242, 241, 0.4);
    text-align: center;
    font-size: 0.8em;
    border-left: 1px solid #4DB6AC;
    border-top: 1px solid #4DB6AC;
}
.styled-table tbody td:first-of-type {
    border-left: 0;
}
.styled-table tbody th {
    background-color: #4DB6AC;
    color: #ffffff;
    text-align: left;
    border-bottom: none;
}
    </style>"""
    
    html += """
    <body>
        <table class="styled-table" style="Width: 25% !important"><caption>System info</caption>
        <tbody>
            <tr><th scope="row">Device Mac</th><td style="border-top: none !important">{}</td></tr>
            <tr><th scope="row">Device IP</th><td>{}</td></tr>
            <tr><th scope="row">Uptime</th><td>{}</td></tr>
        </tbody></table>""".format(deviceMac,ip,uptime,time[4],time[5])
    
    return html