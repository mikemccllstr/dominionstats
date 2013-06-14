#!/usr/bin/python
# -*- coding: utf8 -*-

names = set(['Warlord Bot', 'Warlord Bot I', 'Warlord Bot II', 'Warlord Bot III', 'Villager Bot', 'Villager Bot I', 'Villager Bot II', 'Villager Bot III', 'Banker Bot', 'Banker Bot I', 'Banker Bot II', 'Banker Bot III', 'Village Idiot Bot', 'Village Idiot Bot I', 'Village Idiot Bot II', 'Village Idiot Bot III', 'Lord Bottington', 'Lord Bottington I', 'Lord Bottington II', 'Lord Bottington III', 'Serf Bot', 'Serf Bot I', 'Serf Bot II', 'Serf Bot III', 'Defender Bot', 'Defender Bot I', 'Defender Bot II', 'Defender Bot III', 'Conqueror Bot', 'Conqueror Bot I', 'Conqueror Bot II', 'Conqueror Bot III', #Basic names
    'Alice the Serf', 'Serf Adela', 'Maiden Abigail', 'King Rex', 'Serf Gordon', 'Maiden Marjoria', 'Squire Edwin', 'Queen Vada', 'Distant Cousin', 'Maiden Marie', 'Squire Clayton', 'Lady Sarra', 'Joseph Gelu', 'Overlord Hogan IV', ' Squire Brockton', 'Lady Marigold', 'Gentleman Garrick', 'Concealed Employer', 'Lady Gloriana', 'Gentleman Bradshaw', 'Gentleman Preston', 'Grandmother', #Base Set act 1
    'Soldier', 'Witch Jezebel', 'Bonificaius', 'Sir Robert', 'Prince Arundel', 'Thief', 'Edith', 'Prince'# Manually added
'Alice the Serf', # Andrew Iannacone's Script 
'Captain Althea',
'Cardwell the Serf',
'Galore, the Mountebank',
'Gentleman Akelin',
'Gentleman Albert',
'Gentleman Althalos',
'Gentleman Alvar',
'Gentleman Ashton',
'Gentleman Bradshaw',
'Gentleman Charles',
'Gentleman Davidson',
'Gentleman Drake',
'Gentleman Earl',
'Gentleman Eduardo',
'Gentleman Egric',
'Gentleman Faran',
'Gentleman Gandolf',
'Gentleman Garrick',
'Gentleman Hal',
'Gentleman Harald',
'Gentleman Ivan',
'Gentleman Justin',
'Gentleman Keaton',
'Gentleman Morell',
'Gentleman Norman',
'Gentleman Osric',
'Gentleman Pierson',
'Gentleman Preston',
'Gentleman Searle',
'Gentleman Sedgewick',
'Gentleman Thrall',
'Gentleman Viktor',
'Gentleman Vilin',
'Gentleman Winston',
'Grandfather',
'Grandmother',
'King Leonard',
'King Rex',
'Lady Acelina',
'Lady Amelia',
'Lady Arabella',
'Lady Ayleth',
'Lady Aylild',
'Lady Celestine',
'Lady Christabel',
'Lady Dorcus',
'Lady Elena',
'Lady Felicia',
'Lady Florence',
'Lady Floria',
'Lady Gloriana',
'Lady Godelina',
'Lady Gussalen',
'Lady Hildegard',
'Lady Ida',
'Lady Ingride',
'Lady Juetta',
'Lady Kateryn',
'Lady Lia',
'Lady Maerwynn',
'Lady Marigold',
'Lady Maud',
'Lady Pya',
'Lady Sarra',
'Lady Tilla',
'Lady Vluerona',
'Leroy, King of Infamy',
'Maiden Abigail',
'Maiden Agatha',
'Maiden Chera',
'Maiden Diamanda',
'Maiden Ellyn',
'Maiden Esmaredla',
'Maiden Esther',
'Maiden Ewe',
'Maiden Guinevere',
'Maiden Jacquelyn',
'Maiden Jessica',
'Maiden Joya',
'Maiden Justina',
'Maiden Lettice',
'Maiden Lia',
'Maiden Lindara',
'Maiden Lynna',
'Maiden Marie',
'Maiden Marjoria',
'Maiden Mirabelle',
'Maiden Muriel',
'Maiden Nicholaa',
'Maiden Osanna',
'Maiden Rosamunda',
'Maiden Sarah',
'Maiden Ylaria',
'Overlord Hogan IV',
'Serf Adela',
'Serf Agnes',
'Serf Amiot',
'Serf Anselm',
'Serf Archer',
'Serf Beatrice',
'Serf Catrain',
'Serf Celestria',
'Serf Clarita',
'Serf Crispin',
'Serf Dionisia',
'Serf Eliose',
'Serf Filmore',
'Serf Fleur',
'Serf Frederick',
'Serf Gordon',
'Serf Greta',
'Serf Hague',
'Serf Henna',
'Serf Hunwald',
'Serf Ingrid',
'Serf Mary',
'Serf Matilda',
'Serf Milo',
'Serf Olaf',
'Serf Osred',
'Serf Oswyn',
'Serf Pandonia',
'Serf Rebecca',
'Serf Selda',
'Serf Silban',
'Serf Swale',
'Serf Tilla',
'Serf Willard',
'Serf Ysmay',
'Serf Zebulon',
'Squire Allister',
'Squire Brockton',
'Squire Bryce',
'Squire Chermin',
'Squire Clayton',
'Squire Clifton',
'Squire Denis',
'Squire Edwin',
'Squire Elmo',
'Squire Fabian',
'Squire Hadrian',
'Squire Lance',
'Squire Leik',
'Squire Levi',
'Squire Lyman',
'Squire Matthew',
'Squire Mendel',
'Squire Nuno',
'Squire Quentin',
'Squire Ronin',
'Squire Rylan',
'Squire Saxon',
'Squire Sedgewick',
'Squire Silas',
'Squire Simeon',
'Squire Solomon',
'Squire Stephen',
'Squire Tarquin',
'Squire Taua',
'Squire Terrald',
'Squire Tigra',
'Squire Winter',
'Squire Wolfe',
'Squire Xabier',
'Gentleman Ingvar',
'Gentleman Donald',
'Gentleman Benjamin',
'Gentleman Tristan',
'Gentleman Russell',
'Lady Amethyst',
'Lady Thomasine',
'Lady Colette',
'Lady Ellen',
'Lady Philippa',
'Lady Delchunk',
'Lady Fustaca',
'Lady Jinx',
'Lady Lizzy',
'Lady Margaret',
'Lady Serafi',
'Squire Steven',
'Squire Redwald',
'Squire Kalle',
'Serf Alis',
'Serf Valenia',
'Serf Erik',
'Lord Vaccarino',
'Lord Nimrod',
'Lord Greystone',
'Lord Avan',
'Lord René',
'Lord Tywin',
'Lord Calvin',
'Lord Felik',
'Lord Xaiver',
'King Grappa',
'King Peter',
'Maiden Joanna',
        'Tutor Thomas'])
