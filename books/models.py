from django.db import models
from django.contrib.auth.models import User
import os
import fitz  # PyMuPDF
from PIL import Image
from django.conf import settings


class Event(models.Model):
    """Model for organizing flipbooks by events"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='fa-calendar', help_text="Font Awesome icon class")
    color = models.CharField(max_length=7, default='#FA8112', help_text="Hex color code")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Event'
        verbose_name_plural = 'Events'

    def __str__(self):
        return self.name


class FlipBook(models.Model):
    """Model for storing flipbooks"""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name='flipbooks')
    pdf_file = models.FileField(upload_to='pdfs/')
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)
    total_pages = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'FlipBook'
        verbose_name_plural = 'FlipBooks'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Override save to convert PDF to images and handle thumbnail logic"""
        super().save(*args, **kwargs)

        # Convert PDF to images if not already done
        if self.pdf_file and self.total_pages == 0:
            self.convert_pdf_to_images()

        # Only generate a thumbnail from the first page if no thumbnail is uploaded
        if self.pdf_file and not self.thumbnail:
            self.generate_thumbnail_from_first_page()

    def generate_thumbnail_from_first_page(self):
        """Generate thumbnail from first page if not provided"""
        try:
            pdf_path = self.pdf_file.path
            book_dir = os.path.join(settings.MEDIA_ROOT, 'books', str(self.id))
            os.makedirs(book_dir, exist_ok=True)
            pdf_document = fitz.open(pdf_path)
            if len(pdf_document) > 0:
                page = pdf_document[0]
                mat = fitz.Matrix(1.5, 1.5)
                pix = page.get_pixmap(matrix=mat)
                thumbnail_path = os.path.join(settings.MEDIA_ROOT, 'thumbnails', f'{self.id}_thumb.jpg')
                os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                img_data = pix.tobytes("jpeg", jpg_quality=85)
                with open(thumbnail_path, 'wb') as f:
                    f.write(img_data)
                self.thumbnail = f'thumbnails/{self.id}_thumb.jpg'
                super().save(update_fields=['thumbnail'])
            pdf_document.close()
        except Exception as e:
            print(f"Error generating thumbnail from first page: {e}")
            import traceback
            traceback.print_exc()

    def convert_pdf_to_images(self):
        """Convert PDF pages to images using PyMuPDF"""
        try:
            pdf_path = self.pdf_file.path
            
            # Create directory for this book's pages
            book_dir = os.path.join(settings.MEDIA_ROOT, 'books', str(self.id))
            os.makedirs(book_dir, exist_ok=True)
            
            # Open PDF with PyMuPDF
            pdf_document = fitz.open(pdf_path)
            total_pages = len(pdf_document)
            
            first_page_image = None
            
            # Convert each page to image
            for page_num in range(total_pages):
                page = pdf_document[page_num]
                
                # Render page to image (1.5x zoom for balance of quality and file size)
                mat = fitz.Matrix(1.5, 1.5)
                pix = page.get_pixmap(matrix=mat)
                
                # Save as JPEG with optimized quality
                image_path = os.path.join(book_dir, f'page_{page_num + 1}.jpg')
                
                # Convert to PIL Image for better compression control
                img_data = pix.tobytes("jpeg", jpg_quality=75)
                with open(image_path, 'wb') as f:
                    f.write(img_data)
                
                # Keep first page for thumbnail
                if page_num == 0:
                    first_page_image = image_path
            
            pdf_document.close()
            
            # Update total pages
            self.total_pages = total_pages
            
            # Create thumbnail from first page
            if first_page_image:
                thumbnail_path = os.path.join(settings.MEDIA_ROOT, 'thumbnails', f'{self.id}_thumb.jpg')
                os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
                
                with Image.open(first_page_image) as img:
                    img.thumbnail((300, 400))
                    img.save(thumbnail_path, 'JPEG', quality=85)
                
                self.thumbnail = f'thumbnails/{self.id}_thumb.jpg'
            
            self.save(update_fields=['total_pages', 'thumbnail'])
            print(f"Successfully converted {total_pages} pages")
            
        except Exception as e:
            print(f"Error converting PDF: {e}")
            import traceback
            traceback.print_exc()

    def get_pages(self):
        """Return list of page image URLs"""
        pages = []
        for i in range(1, self.total_pages + 1):
            page_url = f'{settings.MEDIA_URL}books/{self.id}/page_{i}.jpg'
            pages.append(page_url)
        return pages


class BookView(models.Model):
    """Track book views"""
    book = models.ForeignKey(FlipBook, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.book.title} - {self.viewed_at}"


class FlipBookAccess(models.Model):
    """Restrict access to flipbooks for specific users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flipbook_access')
    flipbook = models.ForeignKey(FlipBook, on_delete=models.CASCADE, related_name='user_access')
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'flipbook')
        verbose_name = 'FlipBook Access'
        verbose_name_plural = 'FlipBook Accesses'

    def __str__(self):
        return f"{self.user.username} -> {self.flipbook.title}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    mobile_number = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"
