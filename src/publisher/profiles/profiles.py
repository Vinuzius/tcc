from publisher.profiles.ProfileClass import Profile


PROFILE_A = Profile(
    name="A",
    transform=str.upper,
)

PROFILE_B = Profile(
    name="B",
    transform=str.lower,
)