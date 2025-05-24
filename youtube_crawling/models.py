from django.db import models

class YouTubeVideo(models.Model):
    video_id = models.CharField(max_length=255, unique=True)
    extracted_date = models.CharField(max_length=255)
    upload_date = models.CharField(max_length=255)
    channel_name = models.CharField(max_length=255)
    subscriber_count = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    view_count = models.CharField(max_length=255)
    video_url = models.URLField(unique=True)  # 중복 방지
    product_count = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()

    def __str__(self):
        return self.title


class YouTubeProduct(models.Model):
    video = models.ForeignKey(YouTubeVideo, on_delete=models.CASCADE, related_name='products')
    product_name = models.CharField(max_length=500, blank=True)
    product_price = models.CharField(max_length=100, blank=True)
    product_image_link = models.URLField(max_length=1000, blank=True)
    product_merchant = models.CharField(max_length=100, blank=True)
    product_merchant_link = models.URLField(max_length=1000, blank=True)

    class Meta:
        unique_together = ('video', 'product_name')

    def __str__(self):
        return f"{self.product_name} ({self.product_price})"