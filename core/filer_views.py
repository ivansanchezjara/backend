from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from filer.models import Folder, Image
from .filer_serializers import FolderSerializer, ImageSerializer

class FolderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    
    def get_queryset(self):
        qs = super().get_queryset()
        parent = self.request.query_params.get('parent', 'root')
        if parent == 'root':
            qs = qs.filter(parent__isnull=True)
        elif parent:
            qs = qs.filter(parent_id=parent)
        return qs

class ImageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    parser_classes = (MultiPartParser, FormParser)
    
    def get_queryset(self):
        qs = super().get_queryset()
        folder = self.request.query_params.get('folder', 'root')
        if folder == 'root':
            qs = qs.filter(folder__isnull=True)
        elif folder:
            qs = qs.filter(folder_id=folder)
        return qs

    def create(self, request, *args, **kwargs):
        file_obj = request.data.get('file')
        folder_id = request.data.get('folder')
        
        if not file_obj:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)
            
        folder = Folder.objects.filter(id=folder_id).first() if folder_id else None
        
        image = Image.objects.create(
            file=file_obj,
            original_filename=file_obj.name,
            name=file_obj.name,
            folder=folder,
            owner=request.user
        )
             
        serializer = self.get_serializer(image)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
