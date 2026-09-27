---
hide:
  - toc
---

# OpeningHoursSpecification

A structured value providing information about the opening hours of a place or a certain service inside a place.\n\n The place is __open__ if the [[opens]] property is specified, and __closed__ otherwise.\n\nIf the value for the [[closes]] property is less than the value for the [[opens]] property then the hour range is assumed to span over the next day.

{{ oold_schema_meta_data("schemaorg", "OpeningHoursSpecification") }}

{{ oold_schema_renderer("schemaorg", "OpeningHoursSpecification") }}
