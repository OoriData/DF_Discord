<!------ 0.1.0 -------------------------------------------------------------------------------------------------------->
# 0.1.0


## 🗺️ The map is now four times the resolution!
### 🥾 We've moved around and messed with the roads and trails quite a bit
- This change was made with the aim of making offroad builds and convoys more viable.
- We've removed or degraded several roads and trails, functionally nerfing convoys that can't rough it.
### 🏃 We've sped up tile traversal.
- This speed-up isn't directly proportionally with the increase in world scale The Desolate Frontiers now feel a lot bigger!
### 📈 The basic 3 resoures (⛽️ Fuel, 💧 Water, and 🥪 Food) now have a supply and demand system to their pricing.
- The price of goods going up when there is a shortage, and down when there is oversupply.
- There is *some* baseline generation in all settlements, but especially smaller settlements are now somewhat dependant on player deliveries of basic resources to keep decent stocks.
- We've added over a dozen new `village` settlements.
  - Villages primarily import resources, and don't have many deliveries.
  - Many of sometimes a bit off the beaten path.
  - These make for interesting little diversions, and help bridge some of the gaps left in the newly embiggened map.
  - Villages also generally feature lower prices for resources, although they're also the most sensitive to the supply/demand system.


## 🚘 Vehicles have been heavily reworked!
### 🫆 Vehicle (and brand) names are now original to Desolate Frontiers!
- We didn't want smoke from lawyers, the worst type of smoke.
- There's a lot of fun easter eggs to find. We'll leave it at that, given said lawyerly smoke.

### 🔋 Electric powertrains are now fully supported!
- Electric vehicles consume a new resource, `kWh` (kiloWatt-hours), and can only consume kWh from that vehicle's battery
  - kWh are stored in battery parts, of which a vehicle can only have one.
  - This means you cannot suppliment the battery with extra battery cargo like you can suppliment a vehicle's fuel tank with jerry cans!
- Hybrids are now also supported!
  - We've added several new-to-DF hybrid vehicles that will spawn at various dealerships.
  - And you can also make your own hybrids by adding an internal-combustion drivetrain to an electric vehicle, or an electric drivetrain to an internal-combustion vehicle!
  - Hybrids will expend their electric charge first, and then fall back onto their fuel-internal-combustion drivetrain.
  - This isn't exactly how many real world hybrids work, but we wanted to keep this system simple and easy to understand.
- Electric vehicles charge for free at settlements.
  - Most quickly in domes, and more slowly in smaller settlements.

### ⛽️ Internal-combustion-engines (ICEs) are now swappable!
- Some crate motors also include supporting parts like turbochargers and superchargers.

### 🚛 Trailers have been signifigantly overhauled!
  - Trailers can now be removed from a vehicle at settlement mechanics
  - Trailers now come in 3 flavors
    - Light duty trailers mounted with a Bumper Ball (`bumper` slot coupling part)
    - Medium trailers mounted with a bed mounted Gooseneck hitch (`upfit` slot coupling part)
    - Heavy trailers mounted with a Pintle Hitch & Lunette Ring (`bumper` slot coupling part)
    - Semi trailers mounted with a 2-or-3½-inch Fifth Wheel (`upfit` slot coupling part)
  - There are now several trailers for each coupling type.
    - Including water and fuel tanker trailers.
  - Passenger vehicles cannot haul trailers; traversing the Desolate Frontiers is rough, and nothing short of a proper, frame mounted trailer coupling can handle it.

### 🥊 Vehicles now come in 10 weight classes!
- Some parts have a minimum weight class requirement now, such as trailer couplings.
- Higher weight classes come with caps to a vehicle's 3 basic stats (🌿 Efficiency, 🚀 Top Speed, and 🏔️ Offroad Capability)
  - Hard caps are simple ceilings, simply being the maximum for the stats. this acts similarly to how the current 100 stat limitations work.
  - Soft caps are a point where each additional point in that stat will require 2 of the raw stat. So, a vehicle with a soft limit at 30 will require 36 raw points in Efficiency to acheive a 33 / 100 rating, but a raw Efficiency of 28 will still result in a 28 / 100 rating.
- The weight classes in question:
  - Class 0: *Passenger Vehicles*
    - Hard cap: 100
    - Soft cap: 100
    - No trailers
  - Class 1-2: *Light-Duty Trucks*
    - Hard cap: 100
    - Soft cap: 90
    - Light trailers
  - Class 3-5: *Medium-Duty Trucks & Vans*
    - Hard cap: 90
    - Soft cap: 80
    - Light & Medium trailers
  - Class 6-7: *Heavy-Duty Trucks & Busses*
    - Hard cap: 80
    - Soft cap: 60
    - All trailers
  - Class 8: *Tractors*
    - Hard cap: 70
    - Soft cap: 40
    - All trailers
  - Class 9: *Super Heavy Vehicles*
    - Hard cap: 40
    - Soft cap: 10
    - All trailers
- Weight classes are loosely based on the [US GWVR classes](<https://afdc.energy.gov/data/10380>)
  - But, some vehicles are in a given class for balancing reasons rather than a direct mapping of "vehicle-weight : weight-class". Don't take these too literally.

### ♻️ Vehicles can now be scrapped at a mechanic!
- Scrapping a vehicle costs 1/4 of the value of the vehicle
- Scrapping a vehicle destroys the underlying vehicle, but yeilds any `salvageable` parts.
  - We expect scrapping to be a way for players to get back some of their investment in a vehicle's parts, usually to apply those parts to a bigger, more capable vehicle. For example, you might heavily upgrade your starter vehicle, but eventually have a fleet full of medium-duty trucks, of which one may be a good fit for all of the (salvageable) modifications on your starter. So, you scrap your starter, and apply those parts to a better vehicle.


## :df_plus: Desolate Frontiers +
- DF+ is a subscription that supports ongoing game development while enhancing the gameplay experience with several features.
  - Unlimited Vehicle Management
    - Build convoys of any size
    - Run multiple convoys simultaneously across the wasteland
    - Rename vehicles and convoys for better organization
  - Advanced Logistics
    - Full warehouse functionality for storage and trading
    - Create new convoys directly from warehouses
    - Optimize supply chains across territories
  - Customization Options
    - Design and display syndicate banners
    - Establish faction identity in the wasteland
  - In-game assets remain intact even if a subscription ends
- The core Desolate Frontiers experience remains completely free
  - Free players can command convoys with up to 4 vehicles
  - Free players can operate one convoy in transit at a time
  - Free players can withdraw items from warehouses (but not deposit)
- DF+ includes a referral system
  - When a player uses a referral code and subscribes to DF+, the referring player receives 14 days of free premium access
  - Referral bonuses apply whether the referring player is currently subscribed or not


## 🛠️ Misc minor updates and fixes
- Resource estimation is now much more accurate.
  - This also comes with a fuzz factor on the estimates that you are displayed on the frontend; some future features are going to make exact resource estimation much less reliable.  <!-- move to frontend notes? -->
- Cargo balancing has seen minor updates.
  - This should make hunting down good deliveries a bit less of a priority, although finding a particularly good delivery is still exciting!


## 🐛 Known Bugs
- Top up button is not always working correctly
- Notifications are sometimes duplicated
- The back button occasionally doesn't work when deep in a vendor menu
