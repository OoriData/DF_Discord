

<!------ 0.1.0 -------------------------------------------------------------------------------------------------------->
# 0.1.0


## 📊 Sorting
- Most objects such as cargo and vehicles are now sorted alphabetically


## 🫥 More emojis across the board
- Vehicle emojis are more consistently placed across all menus
- Vendors now have more emojis associated with them in their menus
- Cargo is now better represented by various emoji across all menus


## ⚠️ Improved warnings around journey resource consumption
- kWh consumption displays
- A yellow caution is displayed when the convoy has less than a 2x safety margin needed for the planned journey
- A red error is displayed when the convoy has less than the minimum resources needed for the planned journey
- Fuzzing has been added to the estimates that are displayed
  - Some future features are going to make exact resource estimation much less reliable, so this fuzzing will be more relevant when we get there.


## Vehicle and part display improvements
- Vehicles now display more and better stats, such as
  - Stat hard floors
  - Stat soft caps
  - Stat hard caps
  - Couplings
  - Armor Class
  - Drivetrain type
- Vehicles now indicate if they are electric, and if so, how many kWh they currently have and can maximally hold
- Parts now display all stats


## 🗺️ Map rendering improvements
- The map now renders more clearly and at a higher resolution
  - This was especially needed with the new, much bigger map
- Tile colors have been adjusted for better clarity
  - This also includes a new dark brown tile for `Villages`


## ⛽️ Top-up button improvements
- Top-up button now respects vehicle weight limits and prioritizes topping up lowest stock resources first—no more accidental overloads.


## 🏷️ Sell all cargo button
- All instances of a cargo, across a convoy, can now be sold with one single button


## 🔧 Mechanic menu improvements
- The Mechanic menu now shows part compatibilities much earlier
- The Mechanic menu now has a section for removing parts
- The Mechanic menu now has a section for scrapping vehicles


## 🪪 Usernames can now be changed
- Every player can change their username


## :df_plus: Desolate Frontiers + features
- DF+ players can rename convoys and vehicles, for personality, roleplaying, organization, or just for fun
- Referral code options in the player options menu


## 🐛 Known Bugs
- Top up button is not always working correctly
  - Mitigate by buying resources individually
- Notifications are sometimes duplicated
  - No player mitigation
- `Scrap {VEHICLE} | ${SCRAP_PRICE}` button is sometimes being disabled when it shouldn't be (eg. no cargo, but still disabled)
  - Mitigate by refreshing menu by using `Main Menu` button and then navigating back to scrap menu
- Cargo appears to stay in convoy inventory after being manually sold
  - Mitigate by refreshing menu by using `Main Menu` button and then navigating back to vendor menu
- Vendors with lots of cargo sometimes has that the display for that cargo cut off early
  - No player mitigation
