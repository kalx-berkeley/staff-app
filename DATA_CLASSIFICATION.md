The data that the Radio Pass Giveaway system handles includes

* KALX Stream Server
  * KALX Staff member (which includes some UC Berkeley students) name, email address and phone number
  * On-air pass winner's name, phone number (and in the case of one venue, email address)
  * Venue contact information including name, email address and title
  * Airtable API key granting read access to a view of the KALX Staff Directory which includes staff members name, email address, phone number, photograph (when provided), DJ Name, departments and active status
  * Public data about Venues and Shows such as postal address, date/time, what band is playing and wheelchair accessibility of the venue
* GitHub Action Workflow
  * Netbird setup-key which grants network access to the KALX stream server
  * SSH Private key which grants ssh access to the KALX stream server as the "promotions" user

These data can be categorized in the "UC Berkeley Data and IT Resource Classification Standard". Under this standard the data is classified as described below.

https://security.berkeley.edu/data-classification-standard

* Protection Level P2
  * 300 people's Personally Identifiable Information (name, phone number, email address) which falls under the 500 person limit for P3
* Availability Level A1
  * Loss of availability of the system would prevent giving away passes on-air and calling in pass winners for shows that were closing
* Recovery Level R1
  * As this is an internal staff application it has minimal need for expedited recovery
