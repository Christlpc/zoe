from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Agent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=60)),
                ('prenom', models.CharField(max_length=60)),
                ('telephone', models.CharField(max_length=25, unique=True)),
                ('matricule', models.CharField(max_length=20, unique=True)),
            ],
            options={
                'db_table': 'agents',
                'managed': False,
            },
        ),
    ]
