from publisher.profiles.ProfileClass import Profile


PROFILE_A = Profile(
    name="A",
    transform=str.upper,
)

PROFILE_B = Profile(
    name="B",
    transform=str.lower,
)

PROFILES = {
    PROFILE_A.name: PROFILE_A,
    PROFILE_B.name: PROFILE_B,
}