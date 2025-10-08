from django.shortcuts import render

# Create your views here.
import requests
from decouple import config
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Payment
from rest_framework import viewsets
from .models import Booking
from .serializers import BookingSerializer
from .tasks import send_booking_confirmation


CHAPA_SECRET_KEY = config('CHAPA_SECRET_KEY')

@api_view(['POST'])
def initiate_payment(request):
    data = request.data
    booking_ref = data.get('booking_reference')
    amount = data.get('amount')

    headers = {
        'Authorization': f'Bearer {CHAPA_SECRET_KEY}',
        'Content-Type': 'application/json'
    }

    payload = {
        'amount': str(amount),
        'currency': 'ETB',
        'email': data.get('email'),
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
        'tx_ref': booking_ref,
        'callback_url': 'https://yourdomain.com/verify-payment'
    }

    response = requests.post('https://api.chapa.co/v1/transaction/initialize', json=payload, headers=headers)
    res_data = response.json()

    if res_data.get('status') == 'success':
        Payment.objects.create(
            booking_reference=booking_ref,
            amount=amount,
            transaction_id=res_data['data']['tx_ref'],
            status='Pending'
        )
        return Response(res_data)
    else:
        return Response(res_data, status=400)
@api_view(['GET'])
def verify_payment(request, tx_ref):
    headers = {
        'Authorization': f'Bearer {CHAPA_SECRET_KEY}'
    }

    url = f'https://api.chapa.co/v1/transaction/verify/{tx_ref}'
    response = requests.get(url, headers=headers)
    res_data = response.json()

    try:
        payment = Payment.objects.get(transaction_id=tx_ref)
        if res_data.get('status') == 'success':
            payment.status = 'Completed'
        else:
            payment.status = 'Failed'
        payment.save()
    except Payment.DoesNotExist:
        return Response({'error': 'Payment not found'}, status=404)

    return Response(res_data)
class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def perform_create(self, serializer):
        booking = serializer.save()
        # Trigger Celery task asynchronously
        send_booking_confirmation.delay(booking.customer.email, booking.id)from django.shortcuts import render

# Create your views here.
