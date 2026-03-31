# System description

Fonchi is a distributed real-time seismic signal processing and monitoring system designed to detect and classify seismic events. The system uses a Master-Broker-Slave architecture with frequency analysis to classify events as earthquakes, conventional explosions, nuclear-like events, or base noise. Multiple sensor replicas process signals in parallel, with a centralized broker collecting data and a PostgreSQL database storing analysis results. A real-time NiceGUI frontend displays events, measurements, and replica status through WebSocket streaming.

# User stories

1.  As a client I want to see the events on a dasboard
2.  As a client, I want to know wich are the main events
3.  As a client, for each event, I want to see a dedicated widget
4.  As a client, in each event widget, I want to see, the sensor, frequency, startstamp, endstamp
5.  As a client, I want to be able to refresh the event widget 
6.  As a client, I want to be able to inspect the single event widget.
7.  As a client, I want to inspect the historical events
8.  As a client, I want to see in real time the data transmitted by the sensors
9.  As a client, I want to see a sliding window of the plotted data.
10. As a client, I want to be able to filter the real time data based on the sensor
11. As a client, I want be able to plot the sensor's transmitted data 
12. As a client, I want to see the evolution of the plot in time
13. As a client, I want to be able to hover on the points of the plot and inspect the single value.
14. As a client, I want to be able to export the plot in png format
15. As a client, I want to inspect the historical events on the dashboard
16. As an admin, I want to be able to login
17. As and admin, I want to be able to logout
18. As and admin, I want to be able to see the number of replicas
19. As an admin, I want to see which replicas are alive or not
20. As a client, I want to be notified when the site goes down
