from django.db import models
from django.core.exceptions import ValidationError


class RequestCategory(models.Model):
    """
    Categories for requests with processing functions and hierarchical structure.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    sequence = models.IntegerField(
        help_text="Order in which category processing functions are executed"
    )
    processing_function = models.TextField(
        help_text="Python function code that should return dict with 'category_match' boolean",
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=False,
        help_text="If True, all members have access. If False, only authorized members or groups."
    )
    allowed_channels = models.ManyToManyField(
        'unicom.Channel',
        blank=True,
        related_name='available_categories',
        help_text="Channels where this category can be used. If empty, allowed in all channels."
    )
    authorized_members = models.ManyToManyField(
        'unicom.Member',
        blank=True,
        related_name='directly_accessible_categories',
        help_text="Individual members with explicit access to this category"
    )
    authorized_groups = models.ManyToManyField(
        'unicom.MemberGroup',
        blank=True,
        related_name='accessible_categories',
        help_text="Member groups with access to this category"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['sequence', 'parent']]
        ordering = ['parent_id', 'sequence']
        verbose_name_plural = "Request categories"
        indexes = [
            models.Index(fields=['is_public', 'is_active'], name='category_access_idx')
        ]

    def __str__(self):
        return f"{self.name} ({self.sequence})"

    def clean(self):
        # Ensure sequence is unique within the same parent level
        if RequestCategory.objects.filter(
            parent=self.parent,
            sequence=self.sequence
        ).exclude(id=self.id).exists():
            raise ValidationError(
                'Sequence must be unique for categories with the same parent'
            )

    def process_request(self, request):
        """
        Execute the category's processing function on a request.
        The function should return a dict with at least a 'category_match' boolean
        indicating whether this category matches the request.
        
        Example processing function:
        ```python
        def process(request, metadata):
            # Check if request matches this category
            matches = check_some_condition(request)
            
            # Update metadata as needed
            metadata['some_key'] = 'some_value'
            
            # Must return dict with at least category_match
            return {
                'category_match': matches,
                **metadata
            }
        ```
        """
        try:
            # Create a function object from the processing_function code
            # This should be properly sanitized and executed in a safe context
            local_vars = {'request': request, 'metadata': request.metadata}
            exec(self.processing_function, {}, local_vars)
            
            # Get result and ensure it has category_match
            result = local_vars.get('metadata', {})
            if 'category_match' not in result:
                result['category_match'] = False
                result['error'] = 'Processing function did not return category_match'
            
            return result
        except Exception as e:
            # Log the error and return non-matching result
            print(f"Error processing category {self.name}: {e}")
            return {
                'category_match': False,
                'error': str(e),
                **request.metadata
            } 