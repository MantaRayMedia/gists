#! /bin/bash

# reset it all
iptables -t filter -F 
iptables -t filter -X 

# block all traffic
iptables -t filter -P INPUT DROP 
iptables -t filter -P FORWARD DROP 
iptables -t filter -P OUTPUT DROP 

# keep established connections
iptables -A INPUT -m state --state RELATED,ESTABLISHED -j ACCEPT 
iptables -A OUTPUT -m state --state RELATED,ESTABLISHED -j ACCEPT 

# allow loopback
iptables -t filter -A INPUT -i lo -j ACCEPT 
iptables -t filter -A OUTPUT -o lo -j ACCEPT 

# allow web traffic
iptables -t filter -A OUTPUT -p tcp --dport 80 -j ACCEPT
iptables -t filter -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -t filter -A OUTPUT -p tcp --dport 443 -j ACCEPT
iptables -t filter -A INPUT -p tcp --dport 443 -j ACCEPT

# allow ssh from IP only
iptables -A INPUT -p tcp -m tcp -s 54.171.219.153 --dport 22 -j ACCEPT
iptables -A INPUT -p tcp -m tcp -s 0.0.0.0/0 --dport 22 -j DROP

# allow SOLR from IP only
iptables -A INPUT -p tcp -m tcp -s 54.171.219.153 --dport 8099 -j ACCEPT
iptables -A INPUT -p tcp -m tcp -s 0.0.0.0/0 --dport 8099 -j DROP
iptables -A INPUT -p tcp -m tcp -s 54.171.219.153 --dport 8983 -j ACCEPT
iptables -A INPUT -p tcp -m tcp -s 0.0.0.0/0 --dport 8983 -j DROP


# allow udp only on port 53
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p udp -j DROP
ip6tables -A OUTPUT -p udp -j DROP

# block ping
iptables -A OUTPUT -p icmp --icmp-type echo-request -j DROP
iptables -A INPUT -p icmp --icmp-type echo-request -j REJECT
