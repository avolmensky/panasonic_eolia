# Panasonic Ep;oa HA component

A home assistant custom climate component to control Panasonic Eolia airconditioners.

This component uses the python library `panasoniceolia`

https://github.com/avolmensky/python-panasonic-eolia

## Usage
Add the following configuration in `configuration.yaml`:

```yaml
climate:
  - platform: panasonic_eolia
    username: !secret user
    password: !secret password
```
