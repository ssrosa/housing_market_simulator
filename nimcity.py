import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tqdm.autonotebook import tqdm
import drawSvg as draw
#CONSTANTS:
BLOCK_SIZE = 51000
MIN_RES_SIZE = 425
INFLATION = 0.02

class Council(object):
    '''
    Council acts as a governing body. It zones and rezones districts 
    (in response to user input) and it approves each new construction 
    and demoltion project (as a function of probability input by the user.) 
    The probability function allows for a laissez-faire Council (p = 1) 
    or a capricious, micro-managing one (p = .01).
    '''
    def __init__(self, construct_p, demolish_p):
        self.construct_p = construct_p
        self.demolish_p = demolish_p
    def zone(self, land, to_zone_as):
        land.zoned_as.append(to_zone_as)
    def approve_construction(self, block):
        approval = bool(np.random.binomial(1, self.construct_p))
        return approval
    def approve_demolition(self, block):
        approval = bool(np.random.binomial(1, self.demolish_p))
        return approval

class Developer(object):
    '''
       Developer builds and knocks down buildings. It iterates over the 
       blocks in the sim, constructing or demolishing buildings where 
       conditions permit. It seeks approval from a Council for each new 
       project. It does not respond directly to supply (e.g. quantity of 
       unoccupied housing units) or to demand (e.g. current price per sqft)
       but rather builds or knocks it down what it can as it iterates over 
       the city blocks. The cycle of development in real life is slow enough 
       that in a model like this it makes sense for it to appear random and
       iterative.
    '''
    def __init__(self):
        self.residences_built = []
        self.residences_demolished = []
    def building_approved(self, council, block):
        #Get permission from council to put up a new building.
        approval = council.approve_construction(block)
        return approval      
    def demolition_approved(self, council, block):
        #Get permission from council to demolish a building.
        approval = council.approve_demolition(block) 
        return approval
    def evict_all(self, residence):
        [u.occ[-1].move_out() for u in residence.units[-1] if u.occ[-1]]
    def demolish(self, step, council, residence):
        if self.demolition_approved(council, residence.block):
            #Make all households move out
            self.evict_all(residence)
            #Remove this residence from the block's list and from all records moving forward.
            residence.block.residences[-1].remove(residence)
            #Remove the block from this residence
            residence.demolished = step
        return residence
    
    def build(self, step, council, block, price_sqft):
        if self.building_approved(council, block) and block.has_enough_area_to_build():
            #Buildings in higher-zoned blocks must be somewhat bigger to start with. 
            #(Extremely skinny tall buildings would be strange.)
            max_res_size = block.min_res_size() * (5 * block.zoned_as[-1])
            #If the max size of a building of this type is bigger than the available area
            if max_res_size > block.area_avail():
                #And if the available area is bigger than half hte block size 
                if block.area_avail() > (block.size / 2):
                    #Then the building's max size will be half hte block size
                    max_res_size = (block.size / 2)
                #Or if the available area is less than half the block size
                elif block.area_avail() <= (block.size / 2):
                    #The building's max size will be the available area
                    max_res_size = block.area_avail()
            #Otherwise if max building size is equal to or smaller than area available, no problem
            #Range of possible sizes for the building from min to max
            size_range = np.arange(block.min_res_size(), max_res_size + 1)
            #Give residence a random size within the realm of possibility
            size = np.random.choice(size_range)
            #Instantiate new residence object
            residence = Residence(step, block, size, price_sqft)
            #Add residence to last list of residences built on the block
            block.residences[-1].append(residence)
            return residence
    
class District(object):
    '''
    District is a group of Blocks. ALthough it is heirarchically 'higher'
    than Block, District is instantiated afterward and gets Blocks assigned
    to it rather than setting up its own Blocks upon its own instantiation.
    District gets zoned by a Council and then passes its zoning down onto
    its Blocks. When its zoning changes, the new zone gets updated in all its
    Blocks, each of which may now contain 'underzoned' buildings eligible 
    for demolition.
    '''
    def __init__(self):
        self.zoned_as = []
        self.blocks = [[]]
    def update(self):
        self.zoned_as.append(self.zoned_as[-1])
        #Append last time step's blocks
        #self.blocks.append([b for b in self.blocks[-1]])        
        
class Block(object):
    '''
    Block is the basic unit of buildable land within the sim. Each block
    can only fit as many Residences as its size allows. Block's zoning
    changes when its District's zoning changes. Its buildings built during
    its earlier zoning may thus become 'underzoned' and eligible for 
    demolition. The entire rich history of construction and demolition
    within the sim is recorded in the Blocks' lists.
    '''
    def __init__(self, size):
        self.size = size
        self.district = None
        self.zoned_as = []
        self.residences = [[]]
    def min_res_size(self):
        if not self.zoned_as[-1]:
            raise ValueError('Cannot calculate minimum residence size for an un-zoned block.')
        if self.zoned_as[-1] == 1:
            return MIN_RES_SIZE 
        else:
            #For blocks zoned higher than 1, the minimum size for a building
            #is a little bigger.
            return (MIN_RES_SIZE * (self.zoned_as[-1] / 2))
    def area_built_on(self):
        return sum([r.size for r in self.residences[-1]])
    def area_avail(self):
        return self.size - self.area_built_on()
    def has_enough_area_to_build(self):
        if self.area_avail() >= self.min_res_size():
            return True
        else:
            return False
    def update(self):
        #Update zoning per district's zone
        self.zoned_as.append(self.district.zoned_as[-1])
        #Append last time step's residences
        self.residences.append([r for r in self.residences[-1]])

class Residence(object):
    '''
    Residence is the only building object in the sim. It is built and
    demolished by a Developer (with approval from a Council) on a block. 
    It contains units for Households to live in. A Residence 
    with one Unit is functionally a single-family home. Its "size" is its 
    footprint area on the Block. If zoning allows, a Residence may have several
    floors, each with the same footprint area as the first floor. A multi-story 
    Residence thus may have much greater area for Units than its 'size' 
    would allow in a 1-floor Residence.
    '''
    def __init__(self, step, block, size, price_sqft):
        #Time step when this residence was built by a developer
        self.built = step
        self.price_when_built = price_sqft
        #Time step when this r was demolished by a developer
        self.demolished = None
        #Block that this r is on. (Cannot change.)
        self.block = block
        #Amount of land taken up by building.
        #Are avail for units may be higher depending on zoning.
        #Size cannot change.
        self.size = size
        #Zone cannot change.
        self.zoned_as = self.block.zoned_as[-1]

        #Can have as many floors as allowed by the zoning of the block & district.
        self.floors = 1 if self.zoned_as == 1 else \
                np.random.choice(np.arange(2, self.zoned_as + 1))
        #Fill interior of building with units.
        self.units = [[]]
        self.create_units()
    def create_units(self):
        #Create units for residence
        #Amount of area available for units:
        interior = self.size * self.floors
        #Smallest possible unit size is hard coded as a constant.
        min_unit_size = MIN_RES_SIZE
        #Max unit size is one entire floor of the building
        max_unit_size = self.size
        #Minimum 1 unit per floor
        min_unit_count = interior / max_unit_size
        #Residences zoned as 1 can only have 1 unit
        #Otherwise can have as many units as will fit on the 'size' times the floors
        max_unit_count = 1 if self.zoned_as == 1 else interior // min_unit_size 
        if self.zoned_as != 1:
            unit_count_range = np.arange(min_unit_count, max_unit_count + 1)
            unit_count = np.random.choice(unit_count_range)
        else:
            unit_count = 1
        unit_size = interior / unit_count
        #Actually create the units now
        for i in np.arange(unit_count):
            unit = Unit(self, unit_size, self.price_when_built)
            self.units[-1].append(unit)
    def underzoned(self):
        #Check if this residence is underzoned and eligible for demoliton.
        if self.floors < np.sqrt(self.block.zoned_as[-1]):
            return True
        else:
            return False

class Unit(object):
    '''
    Unit is a living space for Households inside a Residence. A Unit's 
    size is a function of its Residence's zoning, size, and number of
    floors. Each Unit can only have one Household living in it at any time. 
    A Unit may also be 'owned' by its current occupant. A Unit's initial 
    value is a function of the current price per sqft of housing times the 
    Unit's size. A later spike in demand for housing at this price point may 
    cause its value to rise further. The upward trend in a Unit's value thus 
    may become detached from inflation over time depending on demand. 
    (Prices in this sim never fall.)
    '''
    def __init__(self, residence, size, price_sqft):
        #Unit cannot be moved into another building or resized.
        self.residence = residence
        self.size = size
        #Cost to rent/own a unit. Should increase slightly over time
        #with inflation. 
        self.value = [(self.size * price_sqft)]
        #Occupant is a list. -1 is current occupant.
        self.occ = [False]
        #Owner, if any. (Otherwise, rented.)
        self.owned_by = [False]
    def update(self):
        self.value.append(self.value[-1])
        self.value[-1] += self.value[-1] * INFLATION
        self.occ.append(self.occ[-1])
        self.owned_by.append(self.owned_by[-1])
    def spike(self, spike):
        self.value[-1] += (self.value[-1] * spike)
        
class Household(object):
    '''
    Household is the unit of population in the sim. (There are no individual 
    people.) A Household seeks to live in a Unit that it can afford. Once it 
    moves in, it will stay until the value of the Unit rises above the Household's 
    spending power. If a Developer gets approval from a Council to demolish the 
    Residence containing the Household's Unit, the Household will 
    get evicted from the Unit and will seek new housing.
    A Household's spending power (.has) is meant to represent only the portin 
    of its income that it can spend on housing, assumed to be about 1/3 of total income.
    '''
    def __init__(self, has, step):
        #Time step when this household joins the sim
        self.arrived = step
        #Current unit the household is occupying (its 'address')
        #or False if it is not housed.
        self.housed = [False]
        #Whether household owns the unit it is housed in
        self.owns = [False]
        #Household's spending power for housing. Should increase slightly 
        #over time with inflation.
        self.has = [has]
    
    def update(self):
        self.housed.append(self.housed[-1])
        self.owns.append(self.owns[-1])
        self.has.append(self.has[-1])
        self.has[-1] += self.has[-1] * INFLATION 
    
    def can_move_in(self, unit):
        #If household needs a place to live
        #and unit not already taken
        #and household can afford unit 
        if (not self.housed[-1]) \
        and (not unit.occ[-1]) \
        and (unit.value[-1] <= self.has[-1]):        
            return True
        else: 
            return False
    def must_move_out(self):
        #Household has a place to live
        #buts its value has risen above
        #household's spending power
        if (self.housed[-1]) \
        and self.has[-1] < self.housed[-1].value[-1]\
        and not self.owns[-1]:
            return True
        else:
            return False
        
    def move_in(self, unit, own_p):
        #Household becomes occupant of unit
        unit.occ[-1] = self
        #Houshold marks itself as housed
        self.housed[-1] = unit
        #If this is a single family residence (i.e. res with one unit)
        #then there's a chance the hh could own not rent.
        if self.housed[-1].residence.floors == 1:
            own_bool = bool(np.random.binomial(1, own_p))
            #If by chance this household gets to own this unit
            if own_bool:
                #Unit is owned by this household
                self.housed[-1].owned_by[-1] = self
                #This household now owns the unit
                self.owns[-1] = self.housed[-1]
    
    def move_out(self):
        #Unit loses occupant
        self.housed[-1].occ[-1] = False
        #Household marks itself as unhoused
        self.housed[-1] = False
        #If the household owns its unit
        if self.owns[-1]:
            #Unit loses owner
            self.owns[-1].owned_by[-1] = False
            #Owner loses unit
            self.owns[-1] = False
            
class Simulation(object):
    '''
    WHen the Simulation starts it gets filled with people and buildings
    according to the parameters input by the user. Time step 0 in the sim
    is assumed to be the first time step at which the user is modeling an
    existing city, not the time step at which a city is created from scratch.
    (Cities are not built that way.)
    The Simulation runs through its time steps in a 'turned-based' way, with
    each process happening in the same order at every time step so that all the
    objects' lists can update correctly.
    It is assumed that a time step is 1 year. Smaller time increments 
    would be possible--with much greater run times--but some parameters would 
    need to be adjusted for shorter time steps to make sense, e.g. INFLATION
    would need to be scaled down from the generic annual rate of 2%.
    '''
    def __init__(self, 
                 land, zoning, price_sqft,
                 dev_count, init_rounds_of_dev, council_count, construct_p, demolish_p,
                 pop_growth, has_avg, has_std, own_p):
        self.zoning = zoning #Instructions for Council to zone/rezone districts each year
        #Highest zoning
        self.zoning_max = max(set([z for z_dict in self.zoning for k,z in z_dict.items()]))        
        self.price_sqft = [price_sqft] #Price of new housing units
        self.pop_growth = pop_growth #List of increments to increase population by
        self.has_avg = [has_avg] #Average spending power of households
        self.has_std = [has_std] #Standard deviation of spending power for households
        self.own_p = own_p #Probability that a household may own a single-family unit
        self.step = 0 #Time step 0 
        
        print('Simulation started.')

        ### I. LET THERE BE LAND.
        #Fill up land area with blocks.
        blocks = self.create_blocks(land)
        self.blocks = [blocks]
    
        #Map all blocks onto districts as evenly as possible. 
        #This is done randomly, not by a council, just as neighborhoods
        #would coalesce organically in real life.
        districts = self.create_districts(self.blocks[-1])
        self.districts = [districts]
        
        ### II. LET THERE BE GOVERNMENT FOR THE LAND.
        #Create councils.
        #Just one council object for now.
        councils = self.create_councils(council_count, construct_p, demolish_p)
        self.councils = [councils]
        
        #Council object zones all the districts.
        self.round_of_zoning(self.councils[-1][0])
        #Districts pass their new zone onto each of their blocks.
        #(Hereafter, this will be done autoamtically as part of time steps.)
        [b.zoned_as.append(d.zoned_as[-1]) for d in self.districts[-1] for b in d.blocks[-1]]
        
        ### III. LET THERE BE BUILDERS TO BUILD ON THE LAND.
        #Create developers to build residences.
        developers = self.create_developers(dev_count)
        self.developers = [developers]
        #Have developers build new residences.
        #Just one developer for now.
        d = self.developers[-1][0]
        for round_ in range(init_rounds_of_dev):
            self.round_of_developing(self.councils[-1][0], d,  self.blocks[-1])
        #Hack to correct the number of lists of buildings built.
        #Only need this while doing iterative rounds of development here in sim._init__
        d.residences_built = [[d for d_list in d.residences_built for d in d_list]]
        print(f'Developer built {len(d.residences_built[-1])} residences to start.')
        self.residences = [[r for b in self.blocks[-1] for r in b.residences[-1]]]
        self.units = [[u for r in self.residences[-1] for u in r.units[-1]]]
        
        ### IV. LET THERE BE PEOPLE IN THE BUILDINGS ON THE LAND.
        #Create households to come to the city and move in by popping the
        #last value of population growth.
        new_households = self.create_households(self.pop_growth.pop(), 
                               self.has_avg, 
                               self.has_std)
        self.households = [new_households]
        #Households try to move into a housing unit.
        spike, ceiling = self.round_of_moving_in()
        #Hereafter, spike and ceiling are used for responding to unmet demand 
        
        #Print initial statistics.
        print('\n')
        self.print_stats()
        
    def time_step(self, arrivals):
        
        print('\n')
        print(f'Time Step {self.step}')
        print('\n')

        ### 1. Update list of blocks in the sim.
        self.blocks.append([b for b in self.blocks[-1]])
        
        ### 2. Council rezones districts according to its instructions in 'zoning.'
        self.round_of_zoning(self.councils[-1][0])
        
        ### 3. Update each block to reflect its district's most recent zoning.
        [b.update() for b in self.blocks[-1]]
        
        ### 4. Update each existing unit. (Inflation changes its value, &c.)
        #(Can't use self.units master list for this because some of its objects
        #are also on the demolish list. 
        #sim.units master list will update after new round of development.)
        [u.update() for b in self.blocks[-1] for r in b.residences[-1] for u in r.units[-1]]
        #Also update units in demolished residences.
        [u.update() for d in self.developers[-1] for r_list in d.residences_demolished \
             for r in r_list for u in r.units[-1] if r_list]
        
        ### 5.Update list of developers.
        self.developers.append([d for d in self.developers[-1]])
       
        ### 6. Update list of households. (Should be the same as the previous 
        #time step's list. Updating it now allows new households to be added
        # or dropped for this time step.)
        self.households.append([h for h in self.households[-1]])
        
        ### 7. Update each existing household. (Inflation has changed it spending power, &c.)
        [h.update() for h in self.households[-1]]
        
        ### 8. Inflation increases prices.
        #Master price per sqft of any new housing units rises.
        self.price_sqft.append(self.price_sqft[-1] + (self.price_sqft[-1] * INFLATION))
        #Avg and std spending power of any new households rises.
        self.has_avg.append(self.has_avg[-1] + (self.has_avg[-1] * INFLATION))
        self.has_std.append(self.has_std[-1] + (self.has_std[-1] * INFLATION))
        
        ### 9. Create new developers.
        #(Left out for now)
        
        ### 10. Create new households to move to town.
        new_households = self.create_households(arrivals, self.has_avg[-1], self.has_std[-1])
        print(f'{len(new_households)} new households arrived.')
        self.households[-1].extend(new_households)

        ### 11. Build new residences on any empty land.
        self.round_of_developing(self.councils[-1][0], self.developers[-1][0], self.blocks[-1])
        #Manually append the list of all residences to add the new construction.
        self.residences.append([r for b in self.blocks[-1] for r in b.residences[-1]])
        #Manually add units to sim's master list to capture units from new construction.
        self.units.append([u for r in self.residences[-1] for u in r.units[-1]])
        #DELETE
        #total_area = sum([b.size for b in self.blocks[-1]])
        #avail_area = sum(b.area_avail() for b in self.blocks[-1])
        #DELETE
        #print(f'{avail_area} sqft land remaining to build on out of {total_area} sqft.')
        
        ### 12. All unhoused households (incl. those who just moved to town) 
        #look for housing that they can afford.
        spike, ceiling = self.round_of_moving_in()
        
        ### 13. Households who can no longer afford their units 
        #(and who don't own) move out. (Within a given time step no household
        # should move into and out of a unit.)
        self.round_of_moving_out()
        
        ### 14. Developers go around knocking down buildings that could be
        # bigger. (When a block is rezoned at a higher zone, its existing 
        #buildings retain their old zoning. This is the signal for developers 
        #look for.)
        self.round_of_demolishing(self.councils[-1][0], self.developers[-1][0], self.blocks[-1])
        #Should never demolish a building that was built this time step. 
        #(Too confusing.)

        ### 15. Prices spike in response to unmet demand for housing.
        #(Prices of units below the max spending power of the unhoused shoppers 
        #will rise by a certain percent.
        self.respond_to_demand(spike, ceiling)

    def create_councils(self, council_count, construct_p, demolish_p):
        #Create a council to zone blocks and approve construction/ demolition
        councils = []
        for i in range(council_count):
            council = Council(construct_p, demolish_p)
            councils.append(council)
        return councils
            
    def create_blocks(self, land):
        new_blocks = []
        size = BLOCK_SIZE
        while land > 0:
            #Create a new block only if the block size will fit on 
            #the available land left
            if size > land:
                #Need to break the loop here otherwise it keeps
                # running until a random size is drawn that fits 
                #the available remaining land. Could be tiny.
                break
            else:
                #Instantiate a block
                block = Block(size)
                #(Blocks do not get zoned at instantiation.
                #After being distributed among the districts, each district
                #zones it owns blocks.)
                #Reduce available land area by the size of this block
                land -= size
                #Add this block to the list of blocks in the sim
                new_blocks.append(block)
        #Append this list to the list of blocks as the last item        
        return new_blocks

    def create_districts(self, blocks):
        '''
        Map blocks onto districts evenly. A district is created for each dictionary
        of zoning instructions in sim.zoning.
        '''
        blocks_to_assign = [b for b in blocks]
        districts = []
        #Create as many districts as there are sets of zoning arrays
        for z_dict in self.zoning:
            district = District()
            districts.append(district)
        #While there are still blocks to assign
        while blocks_to_assign:
            #For each district
            for d in districts:
                #If the list hasn't run out of values while iterating
                if blocks_to_assign:
                    #Give the first block to the district and remove it from the list of blocks
                    blocks_to_assign[0].district = d
                    d.blocks[-1].append(blocks_to_assign.pop(0))       
                else:
                    break
        return districts

    def create_developers(self, dev_count):
        '''
        Instantiate some number of developer objects.
        '''
        developers = []
        for i in range(dev_count):
            developer = Developer()
            developers.append(developer)
        #Return developers as a list to be stored
        return developers

    def create_households(self, pop_growth, has_avg, has_std):
        '''
        Create some number of households to come to the city.
        '''
        income_dist = np.random.normal(scale = has_std, loc = has_avg, size = pop_growth)
        new_households = [Household(i, self.step) for i in income_dist]
        #Return the new households as a list
        return new_households

    def round_of_zoning(self, council):
        '''
        Takes one council, not a list of councils. Checks if the zoning 
        dictionary corresponding to each district has a key for this time
        step; if so, rezones the district to the value of the key. Otherwise, 
        copies the   district's zoning from the previous time step. (Districts 
        don't have their own update method.)
        '''
        #For all districts and their corresponding dictionary of zoning instructions.
        for district, zs_for_district in zip(self.districts[-1], self.zoning):
            #If this spot in the zoning dictionary for this district is not empty.
            if self.step in zs_for_district.keys():
                #Rezone the district .
                council.zone(district, zs_for_district[self.step])
            else: #Just copy over each district's previous zone.
                district.zoned_as.append(district.zoned_as[-1])
        #In either case, all blocks in each district will get rezoned to match their 
        # district when they update() .
            
    def round_of_developing(self, council, developer, blocks):
        '''
        Iterate over list of developers and call each developer's develop method
        '''
        d = developer
        c = council
        #Return the block if the size of the the block minus the sum of the sizes of all its residences
        #is less than the min res size times the block's zoning; or just the min res size 
        #if the block is zoned as 1.
        blocks_with_land_avail = [b for b in blocks if (b.size - sum(r.size for r in b.residences[-1])) > \
                                    ((MIN_RES_SIZE * (b.zoned_as[-1] / 2)) if b.zoned_as[-1] != 1 else MIN_RES_SIZE)]
        r_built = []
        for b in blocks_with_land_avail:
            #Can build on a block in inverse proportion to the zoning of the block.
            #e.g. Can build 16 times on a zone-1 block, once a zone-16 block.
            build_count = (b.zoned_as[-1] / np.arange(self.zoning_max))
            r_built.extend([d.build(self.step, council, b, self.price_sqft[-1]) for i in build_count])

        #Add residences built to the list for the developer
        #Don't include None types returned by failed attempts at buliding
        d.residences_built.append([r for r in r_built if r])
        print(f'{len(blocks_with_land_avail)} blocks have enough land for new residences.')
        print(f'{len([r for r in r_built if r])} new residences built.')

    def round_of_demolishing(self, council, developer, blocks):
        '''
        Iterate over list of developers and call each developer's 
        demolish method. Demolished residences still exist in the 
        simulation after being demolished. They remain attached to 
        their units and keep their records but they are no longer 
        counted as being on their block.
        '''
        c = council
        d = developer
        #Each residence is eligible for demolition if its floor count 
        #is less than the square root of the zoning of its block. (Should 
        #capture e.g. 1-floor buildings in blocks rezoned as 4, and 3-floor 
        #buildings in blocks rezoned as 16.)
        rs_to_dem = {b: [r for r in b.residences[-1] if r.underzoned()] for b in blocks}
        #Start a list of demolished residences.

        rs_demolished = []
        total_demolishable = sum([1 for k, v in rs_to_dem.items() for r in v])
        if sum([bool(v) for k,v in rs_to_dem.items()]) == 0:
            print('No residences can be demolished.')
        else:
            print(f'{total_demolishable} residences are underzoned and could be demolished.')
            for b, r_list in rs_to_dem.items():
                #If the list is not empty
                if r_list:
                    #Max number of buildings to demolish is inversely proportional to the zoning
                    #of the block. e.g. A zone-16 block gets one, a zone-1 block gets 16, &c.
                    dem_max = np.round((self.zoning_max / b.zoned_as[-1]), 0)
                    #Number of buildings to demolish: the max if there more buildings than this, otherwise
                    #the whole range of buildings available. (Prevents too many from getting demolished at once.)
                    dem_range = np.arange((dem_max if len(r_list) > dem_max else len(r_list)), dtype = np.uint8)
                    #Demolish all the residences within this range.
                    demolished = [d.demolish(self.step, council, r_list[i]) for i in dem_range]
                    #Append demolished rs to the list.
                    rs_demolished.append(demolished)
            #Repeat for each block in the dict. Then        
            #Flatten the list.        
            rs_demolished = [r for r_list in rs_demolished for r in r_list]
            #Append the list to the developer's own list.
            d.residences_demolished.append(rs_demolished)
            print(f'{len(rs_demolished)} residences demolished.')        
        
    def round_of_moving_in(self):
        '''
        Must be called after time_step() has updated unit and 
        household lists, and before round_of_moving_out(). Prepare 
        lists of units available and unhoused households, then call 
        match() to iterate over units to place households in them.
        (What could be a very slow for loop is optimized by preparing 
        shorter lists with only the relevant units and households.)
        '''
        #Empty variables to be updated with info for responding to demand later.
        spike = 0
        ceiling = 0
        #print('Round of moving')
        #print('#Prepare units and households for moving.')
        #Prepare units and households for moving.
        #print('#Step 1: Get units available.')
        #Step 1: Get units available.
        ua = sorted([u for u in self.units[-1] if not u.occ[-1]], \
                            key = lambda u: u.value[-1], reverse = True)
        #print(f'{len(ua)} units available')
        #print('#Step 2: Get households seeking unit.')
        #Step 2: Get households seeking unit.
        hh = sorted([h for h in self.households[-1] if not h.housed[-1]], \
                            key = lambda h: h.has[-1], reverse = True)
        #print(f'{len(hh)} households available')
        #print(f'#Step 3: Exclude any units with value above the max spending power of {hh[0].has[-1]}')
        #Step 3: Exclude any units with value above the max spending power 
        #of the households. (Wouldn't be able to rent to anyone)
        ua = [u for u in ua if u.value[-1] <= hh[0].has[-1]]
        #If list is empty, meaning no units are affordable for the richest household
        if not ua:
            print('No affordable units available for households looking.')
            return spike, ceiling
        print(f'{len(ua)} units available for households looking.')
       # print(f'#Step 4: Exclude any households with spending power less than {ua[0].value[-1]}')
        #Step 4: Exclude any households with spending power less than 
        #the lowest unit value. (Wouldn't be able to find a place.)
        #Keep hh same length as or shorter than ua.
        #(No unit can take more than household so there cannot be more hh than ua.)
        hh = [h for i, h in enumerate(hh) if (h.has[-1] >= ua[-1].value[-1]) and \
                                                                        (i < len(ua))]
        #If list is empty, mmeaning no households can afford what's available
        #This should never happen under the above conditional, but leaving it in for now
        if not hh:
            print('No households looking for units.')
            return spike, ceiling
        print(f'{len(hh)} households can afford the units available.')
        #print('#Step 5: call the match function to move households into units.')
        #Step 5: call the match function to move households into units.
        hh_remaining = self.match(hh, ua, self.own_p)
        
        print(f'{len(hh) - len(hh_remaining)} households out of {len(hh)} found housing.')
        percent_unhoused = len(hh_remaining) / len(hh)
        print(f'{np.round(percent_unhoused, 4)}% of households seeking housing could not find any.')
        
        if percent_unhoused:
            if percent_unhoused < 0.01:
                spike = 0.01
            elif percent_unhoused > 0.2:
                spike = 0.2
            else:
                spike = percent_unhoused
        if hh_remaining:
            ceiling = np.array([h.has[-1] for h in hh_remaining]).max()
        #Return the price spike for unmet demand and the max value housing that can 
        #receive the spike. Prices will rise at end of time step.
        return spike, ceiling

    def match(self, hh_, ua, own_p):
        '''
        Helper function for round of moving. Does the work of matching 
        household to unit. Iterates over units, trying to match each 
        to the highest-value household in the list. If there's a match,
        the household gets popped and the loop moves on to next unit.
        If there's not a match, the loop just moves on to the next unit. 
        A household can take a unit that ncosts less than or equal to
        its spending power. Some rich households may wind up getting 
        cheap units. Units may go untaken; households may go unhoused.
        '''
        #New list to avoid popping the original
        hh = [h for h in hh_]
        #For each unit in list 
        for u in ua:
            #If there are no households left in the list, stop iterating
            if not hh:
                break
            else:
                #If highest-value household can take the unit
                if hh[0].can_move_in(u):
                    #Household gets unit
                    hh[0].move_in(u, own_p)
                    #Household gets removed from list
                    hh.pop(0)
                #Else: no lower-valued households can take this unit. 
                #It goes unoccupied. Move on to the next unit.
                #Simplest fastest way to iterate over all of them!
        return hh

    def respond_to_demand(self, spike, ceiling):
        '''
        After a round of moving in, some households who were able to afford the units 
        on offer may not have gotten a unit. This is unmet demand for housing.
        The percent of households who could afford a unit but couldn't get one becomes
        the 'spike', a percentage up to 20% by which prices will rise.
        The 'ceiling' is the highest price these households would have been able to afford.
        Prices for all units at or below this price 'ceiling' will rise because they are now
        in greater demand.
        '''
        if spike and ceiling:
            print('\n')
            print('Prices spike!')
            print(f'Unmet demand for housing valued less than {ceiling}')
            print(f'leads to a price spike of {spike * 100}% for units at or below this value.')
            #Get all residences whose unit prices were below the 'ceiling' price
            prices_to_spike = [r for r in self.residences[-1] if r.units[-1][0].value[-1] <= ceiling]
            #Each unit's own value updates as a function of the 'spike'
            [u.spike(spike) for r in prices_to_spike for u in r.units[-1]]
            #Number of units whose prices rose
            u_spike_count = sum([1 for r in prices_to_spike for u in r.units[-1]])
            print(f'Prices rise for {u_spike_count} units.')
            #Update master price per sqft as a function of the spike
            self.price_sqft[-1] += self.price_sqft[-1] * spike
            print(f'Price per sqft of new housing also rises to {self.price_sqft[-1]}.')
            print('\n')

    def round_of_moving_out(self):
        '''
        Must be called after round_of_moving_in().
        A given household should only move_in and move_out once per time step.
        '''
        #Iterate over all households. If a household is housed but 
        #can no longer afford its unit, it moves out.
        hh_moved_out_count = sum([1 for h in self.households[-1] if h.housed[-1] and \
                            h.must_move_out()])
        
        [h.move_out() for h in self.households[-1] if h.housed[-1] and \
                            h.must_move_out()]
        
        #Should be zero if no hh move out
        print(f'{hh_moved_out_count} households moved out of their unit.')
            
    def run(self):
        for arrivals in tqdm(self.pop_growth):
            self.step += 1
            self.time_step(arrivals)
            self.print_stats()

    def print_stats(self):
        print(f'At end of time step {self.step}:')
        
        blocked_land_area = sum([b.size for b in self.blocks[-1]])
        print(f'{len(self.districts[-1])} districts containing {len(self.blocks[-1])} blocks on {blocked_land_area} sqft of land.')
        
        unbuilt = np.round((sum([b.area_avail() for b in self.blocks[-1]]) / blocked_land_area), 4)
        print(f'{unbuilt * 100}% of land is unbuilt upon.')
       
        single_family = np.round(sum([1 for b in self.blocks[-1] \
                                      if b.zoned_as[-1] == 1]) / len(self.blocks[-1]), 4)
        print(f'{single_family * 100}% of blocks are zoned for single-family housing.')
       
        residences_count = len(self.residences[-1])
        newly_built = sum([1 for d in self.developers[-1] for r in d.residences_built[-1] if r])
        newly_demolished = sum([1 for d in self.developers[-1] for r in d.residences_demolished[-1] if r]) \
                                if self.developers[-1][0].residences_demolished else 0
        print(f'Developers built {newly_built} residences this time step and demolished {newly_demolished}.')
        print(f'Total residences: {residences_count}.')
       
        units_count = len(self.units[-1])
        units_occ = np.round((sum([1 for u in self.units[-1] if u.occ[-1]]) / units_count), 4)
        units_unocc = np.round((sum([1 for u in self.units[-1] if not u.occ[-1]]) / units_count), 4)    
        print(f'Total units: {units_count}. Occupied: {units_occ * 100}%. Vacant: {units_unocc * 100}%.')
        print(f'Price per sqft of new housing is now {self.price_sqft[-1]}.')
        print(f'Councils: {len(self.councils[-1])}. Developers: {len(self.developers[-1])}.')
        
        total_hh = len(self.households[-1])
        housed = np.round((sum([1 for h in self.households[-1] if h.housed[-1]]) / total_hh), 4)
        unhoused = np.round((sum([1 for h in self.households[-1] if not h.housed[-1]]) / total_hh), 4)
        print(f'Total population of households: {total_hh}. Housed: {housed * 100}%. Unhoused: {unhoused * 100}%.')
        print(f'Average income of new households will be {self.has_avg[-1]}.')
        


class History(object):
    def __init__(self, simulation):
        '''
        History "crunches" the unstructured data scattered throughout the sim,
        all the little lists inside all the objects, into tabular data that can 
        be analyzed and visualized. It does this with list comprehensions. 
        The list comprehensions here call upon the objects' lists using negative 
        indexing. e.g. Year -11, year 0 out of 10, gets the -11th, or the first, 
        value from a has list. Year -1, year 10 out of 10, gets the -1th, or last, 
        value from a has list. &c.
        Some objects enter the sim later than others so not all objects's lists 
        are of equal length. But because all objects are present at the end of the 
        sim, all objects's lists can be indexed starting from the end of time, 
        so to speak, at time step -1.
        If lists have been updated correctly throughout the sim, the indices should 
        never be out of range. e.g. If the spending power of the Households living 
        in the Units of a Residence on a Block in Year 5 are sought, then each 
        Household should have a Year 5 spending power, each Unit should have a 
        Year 5 occupant, the Residence should have Year 5 Units, and the Block 
        should have a Year 5 Residence.
        '''
        sim = simulation
        
        #BY YEAR:
        #Negative indices to use for lists through time
        b_range = np.flip(np.negative(np.arange(len(sim.blocks))) - 1)
        #####FOR EACH DISTRICT BY YEAR
        area_avail_by_district = [] 
        r_count_by_district = [] 
        r_single_u_count_by_district = []
        r_multi_u_count_by_district = []
        r_size_mean_by_district = [] 
        
        u_count_by_district = []
        u_size_mean_by_district = [] 
        u_value_mean_by_district = []
        
        h_count_by_district = []
        h_has_mean_by_district = []
        h_own_counts_by_district = []
        h_rent_counts_by_district = []
        
        for district in sim.districts[-1]:
            #Get area available by district over time
            area_avail_by_district.append([sum([(b.size - sum([r.size for r in b.residences[i]])) \
                     for b in sim.blocks[i] if b.district == district]) for i in b_range])
            #Number of residences by district over time:
            r_counts = [len([r for b in district.blocks[-1] for r in b.residences[i]]) for i in b_range]
            r_count_by_district.append(r_counts)
            #Number of single-unit residences (single-family homes) by district over time:
            r_single_u_counts = [sum([True for b in district.blocks[-1] for r in b.residences[i] \
                                  if len(r.units[-1]) == 1]) for i in b_range]
            r_single_u_count_by_district.append(r_single_u_counts)
            #Number of multi-unit residences by district over time:
            r_multi_u_counts = [sum([True for b in district.blocks[-1] for r in b.residences[i] \
                                  if len(r.units[-1]) > 1]) for i in b_range]
            r_multi_u_count_by_district.append(r_multi_u_counts)
            #Average residence size by district over time:
            #Get sum of unit sizes per residence, not size of each residence
            r_size_sums = [sum([sum([u.size for u in r.units[-1]]) for b in district.blocks[-1] for r in b.residences[i]]) for i in b_range]
            r_size_mean_by_district.append([r_sum / r_count for r_sum, r_count in zip(r_size_sums, r_counts)])
           
            #Number of units by district over time:
            u_counts = [len([u for b in district.blocks[-1] for r in b.residences[i] for u in r.units[-1]]) for i in b_range]
            u_count_by_district.append(u_counts)
            #Average unit size by district over time:
            u_sums = [sum([u.size for b in district.blocks[-1] for r in b.residences[i] for u in r.units[-1]]) for i in b_range]
            u_size_mean_by_district.append([u_sum / u_count for u_sum, u_count in zip(u_sums, u_counts)])
            #Average unit value by district over time:
            u_values = [sum([u.value[i] for b in district.blocks[-1] for r in b.residences[i] for u in r.units[-1]]) for i in b_range]
            u_value_mean_by_district.append([u_value / u_count for u_value, u_count in zip(u_values, u_counts)])
           
            #Number of households in each district over time
            #(Calculated by number of occupied units since each unit has one household)
            h_counts = [sum([True for b in district.blocks[-1] for r in b.residences[i] for u in r.units[-1] if u.occ[i]]) for i in b_range]
            h_count_by_district.append(h_counts)
            #Average spending power of households in each district over time
            h_has_sums = [sum([u.occ[i].has[i] for b in district.blocks[-1] for r in b.residences[i] for u in r.units[-1] if u.occ[i]]) for i in b_range]
            h_has_mean_by_district.append([h_sum / h_count if h_count else 0 for h_sum, h_count in zip(h_has_sums, h_counts)])
            #Home ownership by district
            h_own_counts = [sum([bool(u.occ[i].owns[i]) for b in district.blocks[-1] for r in b.residences[i] for u in r.units[-1] if u.occ[i]]) for i in b_range]
            h_own_counts_by_district.append(h_own_counts)
            #
            h_rent_counts = [sum([1 for b in district.blocks[-1] for r in b.residences[i] for u in r.units[-1] if u.occ[i] and not u.occ[i].owns[i]]) for i in b_range]
            h_rent_counts_by_district.append(h_rent_counts)
            
            
        #List to populate with dataframes for each district
        self.by_districts = []
        for i, district in enumerate(sim.districts[-1]):
            data = np.array([area_avail_by_district[i],
                         r_count_by_district[i], r_single_u_count_by_district[i], r_multi_u_count_by_district[i],
                                 r_size_mean_by_district[i],
                         u_count_by_district[i], u_size_mean_by_district[i], u_value_mean_by_district[i],
                         h_count_by_district[i],  h_has_mean_by_district[i], h_own_counts_by_district[i],
                                h_rent_counts_by_district[i]]).T
            columns = ['empty_land',
                        'r_count', 'r_single_u_count', 'r_multi_u_count', 'r_size_mean',
                       'u_count', 'u_size_mean', 'u_value_mean', 
                       'h_count', 'h_income_mean', 'h_owner_count', 'h_renter_count']
            self.by_districts.append(pd.DataFrame(data = data, columns = columns))
        
        ##### TOTALS BY YEAR
        area_avail = sum(arr for arr in np.array(area_avail_by_district))
        
        #Number of residences
        r_count = [len(r_list) for r_list in sim.residences]
        #Average residence size
        #Use sum of unit sizes for each residence, not residence size
        r_size_mean = [(sum([sum([u.size for u in r.units[-1]]) \
                             for r in r_list]) / len(r_list)) for r_list in sim.residences]
        #Number of single-unit residences each year
        r_single_u_count = [sum([True for r in r_list if len(r.units[-1]) == 1]) for r_list in sim.residences]
        #Number of multi-unit residences each year
        r_multi_u_count = [sum([True for r in r_list if len(r.units[-1]) > 1]) for r_list in sim.residences]
        
        #Number of units
        u_count = [len(u_list) for u_list in sim.units]
        #Average unit size
        u_size_mean = [(sum([u.size for u in u_list]) / len(u_list)) for u_list in sim.units]
        #Negative indices to call on lists of varying lengths
        u_range = np.flip(np.negative(np.arange(len(sim.units))) - 1)
        #u_range does not go into dataframe
        #Average unit value
        u_value_mean = [(sum([u.value[i] for u in sim.units[i]]) / len(sim.units[i])) for i in u_range]
        
        h_count = [len(h_list) for h_list in sim.households]
        #hh_range is negative indices by which to call items from has list in each household.
        
        hh_range = np.flip(np.negative(np.arange(len(sim.households))) - 1)
        #hh_range is not included in the dataframe
        #Only households who were housed at the end of each year
        h_housed = [sum([1 for h in sim.households[i] if h.housed[i]]) for i in hh_range]
        #Only households who were unhoused at the end of each year
        h_unhoused = [sum([1 for h in sim.households[i] if not h.housed[i]]) for i in hh_range]
        #Average income of household by year
        h_has_mean = [sum([h.has[i] for h in sim.households[i]])\
                             / len(sim.households[i]) for i in hh_range]
        #Number of households each year who owned their unit
        h_own_count = [sum([True for h in sim.households[i] if h.owns[i]]) for i in hh_range]
        #Number of households each year who rented their unit
        h_rent_count = [sum([True for h in sim.households[i] \
                             if not h.owns[i] and h.housed[i]]) for i in hh_range]
        
        #Average time household spent living in sim by year
        #(i.e. average 'age' of household by year)
        h_age_mean = [sum([len(h.has[:i]) for h in sim.households[i]]\
                                ) / len(sim.households[i]) for i in hh_range]
        
        data = np.array([area_avail,
                         r_count, r_size_mean, r_single_u_count, r_multi_u_count,
                         u_count, u_size_mean, u_value_mean,
                         h_count, h_housed, h_unhoused, h_has_mean, h_own_count, h_rent_count, h_age_mean
                        ]).T
        columns = ['empty_land',
                    'r_count', 'r_size_mean', 'r_single_u_count', 'r_multi_u_count',
                   'u_count', 'u_size_mean', 'u_value_mean', 
                   'h_count', 'h_housed', 'h_unhoused', 'h_income_mean', 'h_own_count', 'h_rent_count', 'h_age_mean']
        
        self.all_by_year = pd.DataFrame(data = data, columns = columns).rename_axis('Year')
        
    def get_random_hh(self):
        '''
        Generates statistics for a randomly chosen household.
        '''
        hh = np.random.choice(sim.households[-1])
        hh_range = np.flip(np.negative(np.arange(len(hh.housed))) - 1)
        spending_power = hh.has
        spending_on_housing = [hh.housed[i].value[i] if hh.housed[i] else 0 for i in hh_range]
        size_of_housing = [u.size if u else 0 for u in hh.housed]
        districts_zoned_as = [u.residence.block.district.zoned_as[-1] if u else 0 for u in hh.housed]
        random_hh = pd.DataFrame(data = np.array([spending_power, spending_on_housing, size_of_housing, districts_zoned_as]).T,
                               columns = ['spending_power', 'spending_on_housing', 'size_of_housing', 'districts_zoned_as'])
        return random_hh

def draw_residences(drawing, residences, x, y, show_density = False):
    #Hard coded with block 'height' of 5
    residences_sorted = sorted([r for r in residences], key = lambda r: r.size, reverse = True)
    base_y = y
    BLOCK_DEPTH = 5
    max_y = y + BLOCK_DEPTH
    colors = ['dimgray', 'gray', 'darkgray', 'silver', 'lightgray', 'gainsboro', 'whitesmoke', 
          'lightslategray', 'azure', 'oldlace', 'lightcyan', 'palegoldenrod']
    density_colors = {0: 'white', 1: '#FFDEDE', 2: '#FFC7C7', 3: '#FFB7B7', 3: '#FFB2B2',4: '#FFA7A7', 
                       5: '#FFA1A1', 6: '#FF9999', 7: '#FF9090',
                      8: '#FF8C8C', 9: '#FF8686', 10: '#FF8181', 
                      11: '#FD7676', 12: '#FF6B6B', 13: '#FD6464', 14: '#FD5D5D', 15: '#FC5555', 
                      16: '#FD4F4F', 17: '#FD4646',  18: '#F93D3D',  
                      19: '#F93636', 20: '#EB2727', 21: '#E51F1F',  
                      22: '#B21313', 23: '#A10D0D', 24: '#920707', 25: '#6C0404'}
    #Number of floors in each residence
    floor_counts = [r.floors for r in residences_sorted]
    #How many of the 120 points in a 5x24 grid each building gets
    dots = [r.size // 425 for r in residences_sorted]
    #i.e. street frontage in "dots"
    widths = [dot // 5 if (dot // 5) > 0 else 1 for dot in dots]
    #i.e. how far across the depth of the block in "dots".
    #(Most buildings will have a depth of 5, the whole depth of the block.)
    depths = [5 if (dot // 5) > 0 else dot for dot in dots]
    previous_width = 0
    for w, d, f in zip (widths, depths, floor_counts):
        #If the depth of this building plus the previous would exceed the edge of the block
        if (y + d) > max_y:
            #Go back to y of 0, edge the bottom edge of the block
            y = base_y
            #Start to the right of the previous building, not in front of it
            x += previous_width
        fill = np.random.choice(colors) if not show_density else density_colors[f]
        drawing.append(draw.Rectangle(x,y,w,d, 
                                      fill = fill,
                                      stroke_width = '0.1', stroke = 'black'))
        #Width of this building to use next
        previous_width = w
        #Depth of this buidlign to try to put next building in front of
        y += d

def draw_districts(drawing, column_max, blocks, time_step, 
                show_density = False):
#Test of blocks with buildings together

    block = draw.Lines((0), (0),
                      (0), (0 + 5),
                      (0 + 24), (0 + 5),
                      (0 + 24), (0),
                      fill = 'white',
                      close = True,
                      stroke = 'black',
                      stroke_width = '0.2',
                      id = 'block')
    x = 0
    y = 0
    column = 0
    column_max = column_max
    alley = True
    #Draw first block from which to copy the others
    #Second block will actually get drawn on top of this one
    drawing.append(block)
    #for b in sim.districts[-1][0].blocks[-1]:
    for b in blocks:
        #Reset for new row above previous
        if column > column_max:
            column = 0
            x = 0
            if alley:
                y += 6
                alley = False
            elif not alley:
                y += 7
                alley = True
        drawing.append(draw.Use('block', x, y))
        draw_residences(drawing, b.residences[time_step], x, y, show_density)
        x += 26
        column += 1