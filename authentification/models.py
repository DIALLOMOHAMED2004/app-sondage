from django.db import models
from django.contrib.auth.models import User

ROLE_CHOICES = (
    ('creator', 'Créateur de sondage'),
    ('participant', 'Participant'),
)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='participant')

    def __str__(self):
        return f"{self.user.username} Profile"

# Signal pour créer ou mettre à jour automatiquement le Profile
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()
