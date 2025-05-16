from django.db import models

class YouTubeVideo(models.Model):
    video_id = models.CharField(max_length=20, unique=True)
    extracted_date = models.DateField()
    upload_date = models.DateField()
    channel_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    video_url = models.URLField(unique=True)  # 중복 방지
    subscriber_count = models.CharField(max_length=50)
    view_count = models.CharField(max_length=50)
    product_count = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField()

    def __str__(self):
        return self.title


class YouTubeProduct(models.Model):
    video = models.ForeignKey(YouTubeVideo, related_name='products', on_delete=models.CASCADE)
    product_image_link = models.URLField(null=True, blank=True)
    product_name = models.CharField(max_length=255)
    product_price = models.CharField(max_length=100)
    product_link = models.URLField(null=True, blank=True)

    def __str__(self):
        return self.product_name
