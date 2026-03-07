from pydantic import BaseModel


class FeatureBaseSchema(BaseModel):
    """Shared base schema for the feature."""


class FeatureCreateSchema(FeatureBaseSchema):
    """Input schema example."""


class FeatureReadSchema(FeatureBaseSchema):
    """Output schema example."""
