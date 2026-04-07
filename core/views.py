from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import MyTokenObtainPairSerializer


class MyTokenObtainPairView(TokenObtainPairView):
    # Le decimos que use nuestro empaquetador personalizado
    serializer_class = MyTokenObtainPairSerializer
