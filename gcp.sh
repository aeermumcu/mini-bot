#!/bin/bash
# Mini Monitor GCP Helper Script

VM_NAME="mini-monitor"
ZONE="europe-west1-b"

case "$1" in
  status)
    gcloud compute ssh $VM_NAME --zone=$ZONE --tunnel-through-iap --command="systemctl status mini-monitor"
    ;;
  logs)
    gcloud compute ssh $VM_NAME --zone=$ZONE --tunnel-through-iap --command="journalctl -u mini-monitor -n 50 --no-pager"
    ;;
  follow)
    gcloud compute ssh $VM_NAME --zone=$ZONE --tunnel-through-iap --command="journalctl -u mini-monitor -f"
    ;;
  restart)
    gcloud compute ssh $VM_NAME --zone=$ZONE --tunnel-through-iap --command="sudo systemctl restart mini-monitor"
    ;;
  ssh)
    gcloud compute ssh $VM_NAME --zone=$ZONE --tunnel-through-iap
    ;;
  *)
    echo "Usage: ./gcp.sh [command]"
    echo ""
    echo "Commands:"
    echo "  status   - Check if monitor is running"
    echo "  logs     - Show last 50 log lines"
    echo "  follow   - Follow logs in real-time"
    echo "  restart  - Restart the monitor"
    echo "  ssh      - SSH into the VM"
    ;;
esac
