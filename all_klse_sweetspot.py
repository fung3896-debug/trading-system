# -*- coding: utf-8 -*-
"""
all_klse_sweetspot_colab.py — 全马股甜蜜点扫描
规则完全沿用511信号回测验证:共振>=55 + 强势持续度0.60-0.85, period锁定7y
不因为CRSI那边要简化就跟着改
"""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import yfinance as yf
import datetime


# ============================================================
# 股票名字对照表(814支)
# ============================================================
STOCK_NAMES = {
    '0001.KL': 'SCOMNET', '0002.KL': 'KOTRA', '0008.KL': 'WILLOW', '0012.KL': '3A',
    '0029.KL': 'DIGISTA', '0032.KL': 'REDTONE', '0037.KL': 'RGB', '0039.KL': 'GFM',
    '0040.KL': 'OPENSYS', '0041.KL': 'AIMAX', '0043.KL': 'MTRONIC', '0049.KL': 'OCNCASH',
    '0051.KL': 'CUSCAPI', '0054.KL': 'KARYON', '0056.KL': 'NCT', '0058.KL': 'JCBNEXT',
    '0059.KL': 'ECOHLDS', '0064.KL': 'EFFICEN', '0065.KL': 'EFORCE', '0078.KL': 'GDEX',
    '0082.KL': 'GPACKET', '0083.KL': 'NOTION', '0090.KL': 'ELSOFT', '0091.KL': 'PGB',
    '0097.KL': 'VITROX', '0099.KL': 'SCICOM', '0101.KL': 'TMCLIFE', '0104.KL': 'GENETEC',
    '0113.KL': 'MMSV', '0118.KL': 'TRIVE', '0126.KL': 'MICROLN', '0127.KL': 'JHM',
    '0128.KL': 'FRONTKN', '0136.KL': 'GREENYB', '0138.KL': 'ZETRIX', '0143.KL': 'KEYASIC',
    '0146.KL': 'JFTECH', '0149.KL': 'FIBON', '0151.KL': 'KGB', '0157.KL': 'FOCUSP',
    '0159.KL': 'MMM', '0161.KL': 'HEXIND', '0163.KL': 'CAREPLS', '0166.KL': 'INARI',
    '0168.KL': 'BMGREEN', '0172.KL': 'OCK', '0180.KL': 'KTC', '0183.KL': 'SALUTE',
    '0185.KL': 'HSSEB', '0186.KL': 'PTRANS', '0192.KL': 'INTA', '0193.KL': 'KINERGY',
    '0196.KL': 'QES', '0197.KL': 'WEGMANS', '0198.KL': 'GDB', '0200.KL': 'REVENUE',
    '0201.KL': 'NOVA', '0207.KL': 'MESTRON', '0208.KL': 'GREATEC', '0212.KL': 'SDS',
    '0215.KL': 'SLVEST', '0217.KL': 'POWERWL', '0219.KL': 'RL', '0222.KL': 'OPTIMAX',
    '0223.KL': 'SAMAIDEN', '0225.KL': 'SCGBHD', '0229.KL': 'MOBILIA', '0230.KL': 'TELADAN',
    '0239.KL': 'ECOMATE', '0242.KL': 'PPJACK', '0245.KL': 'MNHLDG', '0246.KL': 'CNERGEN',
    '0249.KL': 'LGMS', '0250.KL': 'YXPM', '0253.KL': 'INFOTEC', '0256.KL': 'UMC',
    '0257.KL': 'UNIQUE', '0258.KL': 'AGMO', '0259.KL': 'SNS', '0268.KL': 'L&PBHD',
    '0269.KL': 'DSS', '0270.KL': 'NATGATE', '0276.KL': 'ADB', '0277.KL': 'CLOUDPT',
    '0291.KL': 'CHB', '0296.KL': 'HEGROUP', '1015.KL': 'AMBANK', '1023.KL': 'CIMB',
    '1058.KL': 'MANULFE', '1066.KL': 'RHBBANK', '1082.KL': 'HLFG', '1147.KL': 'GOB',
    '1155.KL': 'MAYBANK', '1163.KL': 'ALLIANZ', '1171.KL': 'MBSB', '1198.KL': 'MAA',
    '1287.KL': 'EXSIMHB', '1295.KL': 'PBBANK', '1481.KL': 'ASB', '1503.KL': 'GUOCO',
    '1538.KL': 'SYMLIFE', '1562.KL': 'SPTOTO', '1589.KL': 'IWCITY', '1619.KL': 'DRBHCOM',
    '1643.KL': 'LANDMRK', '1651.KL': 'MRCB', '1694.KL': 'MENANG', '1724.KL': 'PARAMON',
    '1818.KL': 'BURSA', '1899.KL': 'BKAWAN', '1929.KL': 'CHINTEK', '1961.KL': 'IOICORP',
    '1996.KL': 'KRETAM', '2038.KL': 'NSOP', '2054.KL': 'TDM', '2062.KL': 'HARBOUR',
    '2089.KL': 'UTDPLT', '2097.KL': 'MBRIGHT', '2127.KL': 'COMFORT', '2135.KL': 'GOPENG',
    '2143.KL': 'ECM', '2224.KL': 'SDRED', '2259.KL': 'TALAMT', '2283.KL': 'ZELAN',
    '2291.KL': 'GENP', '2305.KL': 'AYER', '2429.KL': 'TANCO', '2445.KL': 'KLK',
    '2453.KL': 'KLUANG', '2488.KL': 'ABMB', '2542.KL': 'RVIEW', '2569.KL': 'SBAGAN',
    '2593.KL': 'UMCCA', '2607.KL': 'INCKEN', '2658.KL': 'AJI', '2674.KL': 'ALCOM',
    '2682.KL': 'PARKWD', '2739.KL': 'TECHNAX', '2755.KL': 'FCW', '2828.KL': 'CIHLDG',
    '2836.KL': 'CARLSBG', '2852.KL': 'CMSB', '2984.KL': 'FACBIND', '3018.KL': 'OLYMPIA',
    '3026.KL': 'DLADY', '3034.KL': 'HAPSENG', '3042.KL': 'PETRONM', '3069.KL': 'MFCB',
    '3107.KL': 'FIMACOR', '3158.KL': 'YNHPROP', '3174.KL': 'L&G', '3182.KL': 'GENTING',
    '3204.KL': 'GKENT', '3239.KL': 'BJASSET', '3247.KL': 'GUH', '3255.KL': 'HEIM',
    '3298.KL': 'HEXZA', '3301.KL': 'HLIND', '3336.KL': 'IJM', '3379.KL': 'INSAS',
    '3395.KL': 'BJCORP', '3417.KL': 'E&O', '3441.KL': 'JOHAN', '3476.KL': 'KSENG',
    '3514.KL': 'MARCO', '3557.KL': 'ECOFIRS', '3565.KL': 'WCEHB', '3573.KL': 'LIENHOE',
    '3611.KL': 'PGLOBE', '3662.KL': 'MFLOUR', '3689.KL': 'F&N', '3719.KL': 'PANAMY',
    '3743.KL': 'SUNSURIA', '3778.KL': 'MELEWAR', '3794.KL': 'MCEMENT', '3816.KL': 'MISC',
    '3859.KL': 'MAGNUM', '3867.KL': 'MPI', '3883.KL': 'MUDA', '3891.KL': 'MUIIND',
    '3905.KL': 'MULPHA', '3913.KL': 'MUIPROP', '3948.KL': 'DUTALND', '4006.KL': 'ORIENT',
    '4022.KL': 'MAXIM', '4057.KL': 'ASIAPAC', '4065.KL': 'PPB', '4081.KL': 'PMCORP',
    '4162.KL': 'BAT', '4197.KL': 'SIME', '4219.KL': 'BPROP', '4235.KL': 'LIONIND',
    '4243.KL': 'WTK', '4251.KL': 'IBHD', '4286.KL': 'SEAL', '4316.KL': 'SHCHAN',
    '4324.KL': 'HENGYUAN', '4359.KL': 'TURIYA', '4375.KL': 'SMI', '4383.KL': 'JTIASA',
    '4405.KL': 'TCHONG', '4456.KL': 'DNEX', '4464.KL': 'PHB', '4502.KL': 'MEDIA',
    '4596.KL': 'SAPRES', '4634.KL': 'POS', '4677.KL': 'YTL', '4707.KL': 'NESTLE',
    '4715.KL': 'GENM', '4723.KL': 'JAKS', '4731.KL': 'SCIENTX', '4758.KL': 'ANCOMNY',
    '4847.KL': 'EPICON', '4863.KL': 'TM', '4995.KL': 'VERSATL', '5000.KL': 'HUMEIND',
    '5001.KL': 'MIECO', '5005.KL': 'UNISEM', '5006.KL': 'VARIA', '5007.KL': 'CHINWEL',
    '5008.KL': 'HARISON', '5009.KL': 'WTHORSE', '5010.KL': 'TONGHER', '5011.KL': 'MSNIAGA',
    '5012.KL': 'TAANN', '5015.KL': 'APM', '5016.KL': 'WARISAN', '5020.KL': 'GLOMAC',
    '5021.KL': 'AYS', '5022.KL': 'PAOS', '5024.KL': 'HUPSENG', '5025.KL': 'AURO',
    '5026.KL': 'MHC', '5027.KL': 'KMLOONG', '5028.KL': 'HTPADU', '5029.KL': 'FAREAST',
    '5031.KL': 'TIMECOM', '5032.KL': 'BIPORT', '5035.KL': 'KNUSFOR', '5036.KL': 'EDARAN',
    '5037.KL': 'COMPUGT', '5038.KL': 'KSL', '5040.KL': 'MERIDIAN', '5041.KL': 'PBA',
    '5042.KL': 'TSRCAP', '5048.KL': 'YB', '5049.KL': 'CVIEW', '5053.KL': 'OSK',
    '5054.KL': 'TRC', '5056.KL': 'ENGTEX', '5062.KL': 'HUAYANG', '5065.KL': 'ORNA',
    '5066.KL': 'NTPM', '5068.KL': 'LUSTER', '5069.KL': 'BLDPLNT', '5070.KL': 'PRTASCO',
    '5071.KL': 'COASTAL', '5072.KL': 'HIAPTEK', '5073.KL': 'NAIM', '5075.KL': 'PLENITU',
    '5077.KL': 'MAYBULK', '5078.KL': 'M&G', '5079.KL': 'ONEGLOVE', '5080.KL': 'POHKONG',
    '5081.KL': 'EIG', '5084.KL': 'IBRACO', '5085.KL': 'MUDAJYA', '5087.KL': 'MYCRON',
    '5088.KL': 'APEX', '5090.KL': 'MEDIAC', '5094.KL': 'CSCSTEL', '5095.KL': 'HEVEA',
    '5098.KL': 'MASTEEL', '5099.KL': 'CAPITALA', '5100.KL': 'BPPLAS', '5101.KL': 'EVERGRN',
    '5102.KL': 'GCB', '5104.KL': 'CNH', '5105.KL': 'CANONE', '5106.KL': 'AXREIT',
    '5107.KL': 'IQGROUP', '5109.KL': 'YTLREIT', '5110.KL': 'UOAREIT', '5111.KL': 'TWRREIT',
    '5112.KL': 'THPLANT', '5113.KL': 'RSAWIT', '5115.KL': 'ALAM', '5116.KL': 'ALAQAR',
    '5120.KL': 'AMFIRST', '5121.KL': 'HEKTAR', '5123.KL': 'SENTRAL', '5125.KL': 'PANTECH',
    '5126.KL': 'SOP', '5127.KL': 'ARREIT', '5129.KL': 'MELATI', '5130.KL': 'ATRIUM',
    '5131.KL': 'ZHULIAN', '5132.KL': 'DELEUM', '5133.KL': 'PENERGY', '5134.KL': 'SAB',
    '5135.KL': 'SWKPLNT', '5136.KL': 'HEXTECH', '5138.KL': 'HSPLANT', '5139.KL': 'AEONCR',
    '5140.KL': 'TASCO', '5141.KL': 'DAYANG', '5142.KL': 'WASCO', '5143.KL': 'LUXCHEM',
    '5145.KL': 'SEALINK', '5147.KL': 'SAMCHEM', '5148.KL': 'UEMS', '5149.KL': 'TAS',
    '5151.KL': 'HEXTAR', '5152.KL': 'MBL', '5156.KL': 'XDL', '5157.KL': 'SG',
    '5159.KL': 'YOCB', '5160.KL': 'HOMERIZ', '5161.KL': 'JCY', '5162.KL': 'VSTECS',
    '5163.KL': 'SEB', '5165.KL': 'DFCITY', '5166.KL': 'CYBERE', '5167.KL': 'TURBO',
    '5168.KL': 'HARTA', '5169.KL': 'HOHUP', '5171.KL': 'KIMLUN', '5172.KL': 'SINARAN',
    '5173.KL': 'SYGROUP', '5176.KL': 'SUNREIT', '5178.KL': 'INGENIEU', '5180.KL': 'CLMT',
    '5182.KL': 'AVALAND', '5183.KL': 'PCHEM', '5184.KL': 'CYPARK', '5185.KL': 'AFFIN',
    '5186.KL': 'MHB', '5187.KL': 'HBGLOB', '5188.KL': 'CNOUHUA', '5190.KL': 'BENALEC',
    '5191.KL': 'TAMBUN', '5192.KL': 'ECEXCEL', '5195.KL': 'CENSOF', '5196.KL': 'BJFOOD',
    '5197.KL': 'FLBHD', '5198.KL': 'AFUJIYA', '5199.KL': 'HIBISCS', '5200.KL': 'UOADEV',
    '5202.KL': 'MSM', '5204.KL': 'AWANTEC', '5205.KL': 'SENDAI', '5207.KL': 'SBCCORP',
    '5208.KL': 'EITA', '5209.KL': 'GASMSIA', '5210.KL': 'ARMADA', '5211.KL': 'SUNWAY',
    '5212.KL': 'PAVREIT', '5216.KL': 'NEXG', '5218.KL': 'VANTNRG', '5219.KL': 'PESTEC',
    '5220.KL': 'GLOTEC', '5223.KL': 'MENTIGA', '5225.KL': 'IHH', '5226.KL': 'GBGAQRS',
    '5227.KL': 'IGBREIT', '5228.KL': 'ELKDESA', '5230.KL': 'TUNEPRO', '5231.KL': 'PBSB',
    '5232.KL': 'LEONFB', '5235.KL': 'KLCC', '5235SS.KL': 'KLCC', '5236.KL': 'MATRIX',
    '5238.KL': 'AAGB', '5239.KL': 'TITIJYA', '5242.KL': 'SOLID', '5243.KL': 'VELESTO',
    '5246.KL': 'WPRTS', '5247.KL': 'KAREX', '5248.KL': 'BAUTO', '5249.KL': 'IOIPG',
    '5250.KL': 'SEM', '5252.KL': 'SASBADI', '5253.KL': 'ECONBHD', '5255.KL': 'LFG',
    '5257.KL': 'CARIMIN', '5258.KL': 'BIMB', '5259.KL': 'AVANGAAD', '5260.KL': 'OWG',
    '5263.KL': 'SUNCON', '5264.KL': 'MALAKOF', '5265.KL': 'OASIS', '5267.KL': 'XINHWA',
    '5269.KL': 'ALSREIT', '5271.KL': 'PECCA', '5272.KL': 'RANHILL', '5273.KL': 'CHINHIN',
    '5274.KL': 'HLCAP', '5275.KL': 'MYNEWS', '5276.KL': 'DANCO', '5277.KL': 'FPGROUP',
    '5278.KL': 'RHONEMA', '5280.KL': 'KIPREIT', '5281.KL': 'ADVCON', '5283.KL': 'EWICAP',
    '5284.KL': 'LCTITAN', '5285.KL': 'SDG', '5286.KL': 'MI', '5288.KL': 'SIMEPROP',
    '5289.KL': 'TECHBND', '5291.KL': 'HPMT', '5292.KL': 'UWC', '5293.KL': 'AME',
    '5295.KL': 'INNATURE', '5296.KL': 'MRDIY', '5297.KL': 'TJSETIA', '5298.KL': 'OMH',
    '5299.KL': 'IGBCR', '5300.KL': 'YENHER', '5301.KL': 'CTOS', '5302.KL': 'ATECH',
    '5303.KL': 'SWIFT', '5305.KL': 'SENHENG', '5306.KL': 'FFB', '5307.KL': 'AMEREIT',
    '5308.KL': 'SENFONG', '5309.KL': 'ITMAX', '5310.KL': 'KITACON', '5311.KL': 'CEB',
    '5313.KL': 'RADIUM', '5315.KL': 'SKYWLD', '5316.KL': 'MSTGOLF', '5317.KL': 'CPETECH',
    '5318.KL': 'DXN', '5319.KL': 'MKHOP', '5321.KL': 'KEYFIELD', '5322.KL': 'FEYTECH',
    '5323.KL': 'JPG', '5325.KL': 'WELLCHIP', '5326.KL': '99SMART', '5327.KL': 'MEGAFB',
    '5328.KL': 'LWSABAH', '5329.KL': 'AZAMJAYA', '5330.KL': 'TMK', '5331.KL': 'PGLOBAL',
    '5332.KL': 'REACHTEN', '5335.KL': 'HI', '5336.KL': 'CKI', '5337.KL': 'ECOSHOP',
    '5338.KL': 'PARADIGM', '5340.KL': 'UMSINT', '5341.KL': 'LACMED', '5343.KL': 'GENERGY',
    '5345.KL': 'GEOHAN', '5346.KL': 'HOCKSOON', '5347.KL': 'TENAGA', '5348.KL': 'ORKIM',
    '5351.KL': 'EMPIRE', '5352.KL': 'MTTSL', '5356.KL': 'STRATUS', '5357.KL': 'SKYECHIP',
    '5371.KL': 'KIMHIN', '5398.KL': 'GAMUDA', '5401.KL': 'TROP', '5436.KL': 'PERSTIM',
    '5517.KL': 'SHANG', '5533.KL': 'OCB', '5555.KL': 'SUNMED', '5568.KL': 'APB',
    '5576.KL': 'MINHO', '5592.KL': 'GCE', '5606.KL': 'IGBB', '5614.KL': 'NHB',
    '5622.KL': 'PEB', '5649.KL': 'GPHAROS', '5657.KL': 'PARKSON', '5665.KL': 'SSTEEL',
    '5673.KL': 'JSB', '5681.KL': 'PETDAG', '5703.KL': 'MUHIBAH', '5738.KL': 'CHHB',
    '5789.KL': 'LBS', '5797.KL': 'CHOOBEE', '5819.KL': 'HLBANK', '5827.KL': 'OIB',
    '5843.KL': 'KPS', '5878.KL': 'KPJ', '5908.KL': 'DKSH', '5916.KL': 'MSC',
    '5932.KL': 'BPURI', '5983.KL': 'MBMR', '6009.KL': 'P&O', '6012.KL': 'MAXIS',
    '6017.KL': 'SHL', '6033.KL': 'PETGAS', '6041.KL': 'FARLIM', '6068.KL': 'PCCS',
    '6076.KL': 'ENCORP', '6084.KL': 'STAR', '6114.KL': 'MKH', '6139.KL': 'TAKAFUL',
    '6149.KL': 'METROD', '6173.KL': 'BDB', '6181.KL': 'MALTON', '6203.KL': 'KHEESAN',
    '6211.KL': 'KIALIM', '6254.KL': 'PDZ', '6262.KL': 'INNO', '6297.KL': 'BOXPAK',
    '6351.KL': 'AMWAY', '6378.KL': 'BEDI', '6399.KL': 'ASTRO', '6432.KL': 'APOLLO',
    '6459.KL': 'MNRB', '6483.KL': 'KENANGA', '6491.KL': 'KFIMA', '6521.KL': 'SURIA',
    '6556.KL': 'ANNJOO', '6599.KL': 'AEON', '6602.KL': 'BCB', '6633.KL': 'LHI',
    '6637.KL': 'PNEPCB', '6718.KL': 'CRESNDO', '6742.KL': 'YTLPOWR', '6769.KL': 'JKGLAND',
    '6807.KL': 'PUNCAK', '6815.KL': 'EUPE', '6874.KL': 'JAGCPTL', '6888.KL': 'AXIATA',
    '6904.KL': 'SUBUR', '6912.KL': 'PASDEC', '6939.KL': 'FIAMMA', '6947.KL': 'CDB',
    '6963.KL': 'VS', '6971.KL': 'KOBAY', '6998.KL': 'BINTAI', '7003.KL': 'Y&G',
    '7004.KL': 'MCEHLDG', '7005.KL': 'BIG', '7006.KL': 'RKI', '7007.KL': 'ARK',
    '7010.KL': 'PTT', '7013.KL': 'HUBLINE', '7014.KL': 'YLI', '7016.KL': 'CHUAN',
    '7017.KL': 'KOMARK', '7018.KL': 'CME', '7020.KL': 'ASTEEL', '7022.KL': 'GTRONIC',
    '7025.KL': 'WOODLAN', '7028.KL': 'ZECON', '7029.KL': 'MASTER', '7031.KL': 'AMTEL',
    '7033.KL': 'HIGHTEC', '7034.KL': 'TGUAN', '7035.KL': 'CCK', '7036.KL': 'BORNOIL',
    '7043.KL': 'XIN', '7047.KL': 'FBG', '7048.KL': 'ATLAN', '7050.KL': 'WONG',
    '7052.KL': 'PADINI', '7053.KL': 'SEEHUP', '7054.KL': 'AASIA', '7055.KL': 'PLB',
    '7060.KL': 'NHFATT', '7062.KL': 'KHIND', '7066.KL': 'YONGTAI', '7070.KL': 'VIZIONE',
    '7071.KL': 'OCR', '7073.KL': 'SEACERA', '7076.KL': 'CBIP', '7077.KL': 'KPPROP',
    '7078.KL': 'AZRB', '7079.KL': 'TWL', '7080.KL': 'PERMAJU', '7081.KL': 'PHARMA',
    '7082.KL': 'M&A', '7083.KL': 'ANALABS', '7084.KL': 'QL', '7085.KL': 'LTKM',
    '7086.KL': 'ABLEGRP', '7087.KL': 'MAGNI', '7088.KL': 'POHUAT', '7089.KL': 'LIIHEN',
    '7091.KL': 'UNIMECH', '7094.KL': 'EUROSP', '7095.KL': 'PIE', '7096.KL': 'JOE',
    '7097.KL': 'TAWIN', '7099.KL': 'MAYU', '7100.KL': 'UCHITEC', '7103.KL': 'SPRITZER',
    '7105.KL': 'HCK', '7106.KL': 'SUPERMX', '7107.KL': 'OFI', '7108.KL': 'PERDANA',
    '7113.KL': 'TOPGLOV', '7114.KL': 'DNONCE', '7115.KL': 'SKBSHUT', '7117.KL': 'CJCEN',
    '7120.KL': 'AXTERIA', '7121.KL': 'XL', '7123.KL': 'MAXLAND', '7128.KL': 'CAMRES',
    '7129.KL': 'ASIAFLE', '7131.KL': 'ACME', '7132.KL': 'SMISCOR', '7133.KL': 'ULICORP',
    '7134.KL': 'PWF', '7137.KL': 'UMS', '7139.KL': 'NICE', '7140.KL': 'OKA',
    '7145.KL': 'TXCD', '7146.KL': 'AEM', '7148.KL': 'DPHARMA', '7149.KL': 'ENGKAH',
    '7152.KL': 'JAYCORP', '7153.KL': 'KOSSAN', '7154.KL': 'NEXGBINA', '7155.KL': 'SKPRES',
    '7157.KL': 'CYL', '7160.KL': 'PENTA', '7161.KL': 'KERJAYA', '7162.KL': 'ASTINO',
    '7163.KL': 'PJBUMI', '7165.KL': 'VELOCITY', '7167.KL': 'ABLEGLOB', '7168.KL': 'PRG',
    '7169.KL': 'DOMINAN', '7170.KL': 'LFECORP', '7172.KL': 'PMBTECH', '7173.KL': 'TOYOVEN',
    '7174.KL': 'CAB', '7176.KL': 'TPC', '7178.KL': 'YSPSAH', '7179.KL': 'LAGENDA',
    '7180.KL': 'SERNKOU', '7181.KL': 'ARBB', '7184.KL': 'G3', '7186.KL': 'SWSCAP',
    '7187.KL': 'CHGP', '7188.KL': 'BTM', '7191.KL': 'ADVENTA', '7192.KL': 'GIIB',
    '7195.KL': 'BNASTRA', '7197.KL': 'GESHEN', '7198.KL': 'DPS', '7199.KL': 'KEINHIN',
    '7200.KL': 'TEKSENG', '7201.KL': 'PICORP', '7202.KL': 'HEXRTL', '7203.KL': 'WANGZNG',
    '7204.KL': 'D&O', '7207.KL': 'SUCCESS', '7208.KL': 'EURO', '7209.KL': 'CHEETAH',
    '7210.KL': 'FM', '7211.KL': 'TAFI', '7212.KL': 'DESTINI', '7214.KL': 'ARANK',
    '7215.KL': 'NIHSIN', '7216.KL': 'KAWAN', '7217.KL': 'EMETALL', '7218.KL': 'ARKA',
    '7219.KL': 'AIZO', '7221.KL': 'BSLCORP', '7222.KL': 'IMASPRO', '7223.KL': 'JADI',
    '7225.KL': 'PA', '7226.KL': 'WATTA', '7227.KL': 'UMSNGB', '7228.KL': 'T7GLOBAL',
    '7229.KL': 'FAVCO', '7230.KL': 'TOMEI', '7231.KL': 'WELLCAL', '7232.KL': 'RESINTC',
    '7233.KL': 'DUFU', '7234.KL': 'LOTUSCIR', '7235.KL': 'SUPERLN', '7237.KL': 'PWROOT',
    '7239.KL': 'SCNWOLF', '7240.KL': 'IHB', '7241.KL': 'NGGB', '7243.KL': 'MAGMA',
    '7245.KL': 'CITAGLB', '7246.KL': 'SIGN', '7247.KL': 'SCGM', '7248.KL': 'SLP',
    '7249.KL': 'SKYGATE', '7250.KL': 'UZMA', '7252.KL': 'TEOSENG', '7253.KL': 'HANDAL',
    '7277.KL': 'DIALOG', '7285.KL': 'TOMYPAK', '7293.KL': 'YINSON', '7315.KL': 'AHB',
    '7323.KL': 'KEN', '7374.KL': 'TIENWAH', '7382.KL': 'GLBHD', '7412.KL': 'SHH',
    '7439.KL': 'TECGUAN', '7471.KL': 'EDEN', '7498.KL': 'RALCO', '7501.KL': 'HARNLEN',
    '7528.KL': 'DKLS', '7544.KL': 'QUALITY', '7579.KL': 'AWC', '7595.KL': 'MGB',
    '7609.KL': 'AJIYA', '7617.KL': 'MAGNA', '7668.KL': 'BESHOM', '7676.KL': 'GCAP',
    '7692.KL': 'MYTECH', '7722.KL': 'ASIABRN', '7757.KL': 'UPA', '7765.KL': 'RAPID',
    '7773.KL': 'EPMB', '7803.KL': 'HEXCARE', '7811.KL': 'SAPIND', '7854.KL': 'TIMWELL',
    '7889.KL': 'THRIVEN', '7935.KL': 'MILUX', '7943.KL': 'GREENTEC', '7986.KL': 'CNASIA',
    '8044.KL': 'CFM', '8052.KL': 'CGB', '8079.KL': 'LEESK', '8117.KL': 'PGF',
    '8133.KL': 'BHIC', '8141.KL': 'MJPERAK', '8176.KL': 'WAVEFRNT', '8192.KL': 'MERCURY',
    '8206.KL': 'ECOWLD', '8273.KL': 'PPHB', '8303.KL': 'LOTUS', '8311.KL': 'PESONA',
    '8338.KL': 'DATAPRP', '8346.KL': 'PRKCORP', '8362.KL': 'KYM', '8397.KL': 'TNLOGIS',
    '8419.KL': 'PANSAR', '8435.KL': 'CEPCO', '8443.KL': 'HIL', '8478.KL': 'HWATAI',
    '8486.KL': 'LIONPSIM', '8494.KL': 'LBICAP', '8524.KL': 'TALIWRK', '8532.KL': 'PERTAMA',
    '8567.KL': 'SALCON', '8583.KL': 'MAHSING', '8591.KL': 'CRESBLD', '8605.KL': 'FIHB',
    '8613.KL': 'ENRA', '8621.KL': 'LPI', '8648.KL': 'JASKITA', '8664.KL': 'SPSETIA',
    '8672.KL': 'KAMDAR', '8702.KL': 'TEXCHEM', '8745.KL': 'S&FCAP', '8869.KL': 'PMETAL',
    '8877.KL': 'EKOVEST', '8885.KL': 'AVI', '8893.KL': 'MKLAND', '8907.KL': 'EG',
    '8923.KL': 'JIANKUN', '8966.KL': 'TECHBASE', '8982.KL': 'CEPAT', '9008.KL': 'OMESTI',
    '9016.KL': 'EKSONS', '9059.KL': 'TSH', '9075.KL': 'THETA', '9083.KL': 'JETSON',
    '9091.KL': 'EMICO', '9113.KL': 'ICONIC', '9121.KL': 'KPSCB', '9148.KL': 'GBAY',
    '9172.KL': 'FPI', '9199.KL': 'LYSAGHT', '9237.KL': 'SCIB', '9261.KL': 'GADANG',
    '9288.KL': 'BONIA', '9296.KL': 'RCECAP', '9318.KL': 'FITTERS', '9326.KL': 'LBALUM',
    '9334.KL': 'KESM', '9369.KL': 'TGL', '9377.KL': 'FSBM', '9385.KL': 'LAYHONG',
    '9393.KL': 'ITRONIC', '9407.KL': 'PARAGON', '9423.KL': 'CWG', '9431.KL': 'SJC',
    '9466.KL': 'KKB', '9539.KL': 'MUH', '9571.KL': 'MITRA', '9598.KL': 'PTARAS',
    '9601.KL': 'HWGB', '9628.KL': 'LEBTECH', '9679.KL': 'WCT', '9687.KL': 'IDEAL',
    '9695.KL': 'PLS', '9717.KL': 'SYCAL', '9741.KL': 'ROHAS', '9776.KL': 'RSSB',
    '9792.KL': 'SEG', '9814.KL': 'BERTAM', '9822.KL': 'SAM', '9873.KL': 'PRESTAR',
    '9881.KL': 'LSTEEL', '9938.KL': 'BRIGHT', '9946.KL': 'ETA', '9954.KL': 'RGTBHD',
    '9962.KL': 'GMUTUAL', '9997.KL': 'PENSONI',
}

# ============================================================
# 参数 —— 与511信号回测保持一致，不要随意改动
# ============================================================
RESONANCE_TH = 55
RED_LOW, RED_HIGH = 0.60, 0.85
WARN_HIGH = 0.85
PERSIST_WINDOW_MONTHS = 18
PERIOD = "7y"

BANKER_PERIOD, BANKER_BASE, BANKER_SENS = 50, 50.0, 1.4
HOT_PERIOD, HOT_BASE, HOT_SENS = 40, 30.0, 0.65
STRONG_TH, MEDIUM_TH = 14.0, 7.0
_MIN_TF_LEN = max(BANKER_PERIOD, HOT_PERIOD) + 10  # 60

# ============================================================
# 股票池 —— 全马股(12板块去重合并)
# ============================================================
industrial_list_1 = ["0151.KL","5340.KL","7233.KL","8869.KL","7095.KL","7163.KL","0099.KL","5330.KL","4731.KL","0270.KL","5220.KL","5010.KL","7247.KL","0225.KL","8435.KL","6971.KL","5371.KL","5916.KL","7854.KL","5183.KL","6556.KL","7115.KL","5094.KL","0296.KL","5797.KL","7099.KL","8648.KL","7811.KL","3794.KL","5317.KL","5015.KL","4243.KL","5152.KL","0196.KL","5331.KL","7207.KL","5125.KL","7034.KL","5065.KL","0039.KL","5322.KL","9881.KL","3107.KL","7217.KL","7133.KL","8443.KL","5147.KL","5284.KL","5311.KL","3247.KL","3778.KL","7225.KL","7050.KL","7017.KL","7097.KL"]
industrial_list_2 = ["7214.KL","9873.KL","5098.KL","5277.KL","7245.KL","9121.KL","5134.KL","9199.KL","7029.KL","8117.KL","7076.KL","7137.KL","5192.KL","5436.KL","7227.KL","5001.KL","0161.KL","8273.KL","5298.KL","5276.KL","9148.KL","3298.KL","5007.KL","5163.KL","3883.KL","8419.KL","5072.KL","5665.KL","5198.KL","7173.KL","5197.KL","7014.KL","0269.KL","0291.KL","0207.KL","9237.KL","5095.KL","7201.KL","0257.KL","5232.KL","8044.KL","8745.KL","5048.KL","7073.KL","0064.KL","5009.KL","7114.KL","5068.KL","7188.KL","5087.KL","7221.KL","9318.KL","5037.KL","7096.KL","7018.KL"]
industrial_list_3 = ["0043.KL","7036.KL","3395.KL","4758.KL","5101.KL","7235.KL","5105.KL","7083.KL","5178.KL","7123.KL","7165.KL","6998.KL","7986.KL","0054.KL","7170.KL","7285.KL","6637.KL","7086.KL","9601.KL","4235.KL","5291.KL","5208.KL","5143.KL","6211.KL","9741.KL","6297.KL","9083.KL","9016.KL","0149.KL","5021.KL","6963.KL","5673.KL","5167.KL","0268.KL","5289.KL","5165.KL","7248.KL","9326.KL","7609.KL","7222.KL","7692.KL","7773.KL","7157.KL","7241.KL","5308.KL","7498.KL","7374.KL","2984.KL","7025.KL","6904.KL","5271.KL","8702.KL","0058.KL","7229.KL","5000.KL"]
industrial_list_4 = ["7005.KL","7132.KL","5151.KL","7212.KL","7140.KL","5035.KL","7232.KL","8486.KL","2127.KL","9938.KL","7043.KL","5219.KL","7020.KL","7219.KL","7146.KL","5568.KL","8176.KL","5576.KL","5843.KL","5302.KL","5273.KL","8907.KL","7100.KL","7231.KL","7197.KL","7155.KL","7004.KL","9954.KL","7162.KL","6874.KL","0185.KL","7033.KL","8362.KL","7192.KL","5100.KL","7016.KL","7579.KL","6491.KL","2852.KL","5327.KL","2674.KL","6149.KL","7239.KL","3034.KL","5056.KL","3476.KL","9466.KL","7544.KL","7169.KL","7199.KL","7226.KL","7091.KL","5211.KL","9822.KL","7172.KL"]
energy_list = ["7277.KL","7293.KL","0215.KL","5210.KL","5243.KL","5141.KL","5255.KL","5199.KL","0168.KL","5321.KL","3042.KL","0193.KL","4324.KL","0223.KL","5218.KL","5071.KL","5142.KL","5186.KL","5184.KL","5132.KL","7108.KL","7228.KL","7250.KL","5133.KL","5343.KL","8613.KL","5614.KL","5115.KL","0219.KL","5257.KL","0091.KL","0118.KL","2739.KL","7253.KL"]
healthcare_list = ["5225.KL","5555.KL","5878.KL","7113.KL","5168.KL","7153.KL","7081.KL","7148.KL","7106.KL","0101.KL","0002.KL","0001.KL","7178.KL","0222.KL","5341.KL","0256.KL","0201.KL","7803.KL","0163.KL","7191.KL"]
transport_list = ["3816.KL","5246.KL","5032.KL","5352.KL","5136.KL","5173.KL","5348.KL","0078.KL","2062.KL","6521.KL","8397.KL","5259.KL","5303.KL","7210.KL","5077.KL","5140.KL","8133.KL","5078.KL","4634.KL","5145.KL","7013.KL","5149.KL","7117.KL","7053.KL","7676.KL","8346.KL","5267.KL","7218.KL","6254.KL"]
utilities_list = ["5347.KL","6742.KL","6033.KL","4677.KL","5209.KL","5264.KL","3069.KL","5272.KL","8524.KL","5041.KL","8567.KL","7471.KL"]
tech_list = ["0097.KL","3867.KL","0128.KL","0166.KL","5005.KL","5292.KL","0208.KL","0138.KL","5357.KL","5286.KL","5309.KL","7160.KL","5356.KL","5162.KL","4456.KL","5301.KL","5216.KL","0259.KL","5161.KL","0146.KL","7204.KL","0276.KL","0246.KL","0104.KL","0083.KL","5204.KL","0127.KL","0277.KL","0249.KL","5028.KL","9334.KL","7022.KL","9008.KL","0090.KL","0008.KL","0040.KL","0253.KL","5195.KL","9377.KL","0258.KL","0065.KL","0051.KL","0041.KL","0126.KL","5011.KL","5036.KL","9075.KL","0113.KL","8338.KL","4359.KL","0143.KL","0200.KL","7181.KL","0029.KL","9393.KL"]
reit_list = ["5235.KL","5227.KL","5176.KL","5212.KL","5106.KL","5180.KL","5109.KL","5299.KL","5338.KL","5116.KL","5123.KL","5280.KL","5307.KL","5110.KL","5269.KL","5121.KL","5130.KL","5120.KL","5127.KL","5111.KL"]
construction_list = ["5398.KL","5263.KL","3336.KL","7161.KL","7195.KL","3565.KL","5293.KL","8052.KL","9679.KL","8877.KL","0198.KL","5329.KL","9571.KL","5171.KL","5703.KL","5006.KL","5310.KL","8311.KL","7595.KL","0192.KL","5932.KL","4723.KL","5205.KL","9598.KL","7528.KL","5253.KL","3204.KL","5085.KL","9261.KL","7071.KL","7047.KL","5054.KL","5345.KL","9628.KL","5172.KL","5281.KL","4847.KL","8591.KL","5070.KL","5226.KL","7028.KL","6807.KL","5297.KL","5190.KL","9717.KL","7070.KL","7078.KL","5622.KL","2283.KL","5129.KL","7240.KL","8192.KL","7145.KL","5042.KL","5169.KL","0245.KL"]
finance_list = ["1155.KL","1295.KL","1023.KL","5819.KL","1066.KL","1015.KL","1082.KL","2488.KL","1818.KL","8621.KL","5185.KL","1171.KL","5258.KL","1163.KL","5139.KL","6139.KL","6459.KL","9296.KL","5274.KL","0242.KL","5325.KL","3379.KL","6483.KL","1058.KL","5228.KL","7082.KL","5230.KL","6009.KL","5088.KL","2143.KL","1198.KL","3441.KL"]
plantation_list = ["5285.KL","1961.KL","2445.KL","2089.KL","1899.KL","5323.KL","2291.KL","5126.KL","5027.KL","5012.KL","5029.KL","5138.KL","9059.KL","1996.KL","5069.KL","2593.KL","5135.KL","4383.KL","6262.KL","1929.KL","5319.KL","2569.KL","5112.KL","2453.KL","2038.KL","7501.KL","5026.KL","2054.KL","2135.KL","5113.KL","3948.KL","8982.KL","2542.KL","2607.KL","9695.KL","4316.KL","7054.KL","7382.KL","5223.KL"]
property_list_1 = ["5040.KL","9539.KL","7007.KL","8923.KL","6041.KL","2682.KL","6076.KL","8494.KL","7889.KL","4375.KL","7131.KL","1147.KL","5738.KL","3573.KL","4596.KL","8141.KL","4464.KL","6173.KL","9814.KL","5207.KL","7003.KL","7066.KL","7765.KL","5062.KL","7323.KL","7055.KL","9962.KL","2259.KL","7120.KL","6602.KL","6815.KL","6912.KL","3913.KL","1538.KL","6181.KL","7198.KL","7079.KL","4057.KL","3158.KL","8893.KL","2224.KL","4022.KL","1589.KL","6769.KL","5182.KL","7077.KL","3743.KL","5020.KL","7249.KL","5239.KL","7617.KL","4286.KL"]
property_list_2 = ["5049.KL","5191.KL","5073.KL","5315.KL","3557.KL","4251.KL","6378.KL","5283.KL","1694.KL","3174.KL","2305.KL","6017.KL","5075.KL","3611.KL","5084.KL","1724.KL","0230.KL","5789.KL","7010.KL","1503.KL","3239.KL","5827.KL","6718.KL","7179.KL","6114.KL","0056.KL","7105.KL","1651.KL","7187.KL","3417.KL","9687.KL","5313.KL","2429.KL","5236.KL","8583.KL","5401.KL","5148.KL","5038.KL","5200.KL","5606.KL","8664.KL","5053.KL","8206.KL","5288.KL","5249.KL"]
consumer_list_1 = ["5202.KL","7315.KL","7208.KL","9091.KL","1643.KL","0197.KL","5336.KL","5231.KL","7168.KL","7186.KL","7176.KL","5102.KL","9407.KL","7174.KL","0186.KL","5328.KL","7943.KL","1287.KL","9369.KL","7152.KL","7094.KL","7048.KL","7216.KL","0212.KL","4715.KL","6599.KL","7237.KL","3662.KL","7087.KL","5131.KL","3689.KL","2658.KL","4162.KL","4006.KL","5681.KL","2828.KL","7052.KL","5296.KL","7129.KL","7121.KL","9288.KL","5517.KL","6633.KL","5159.KL","4995.KL","7211.KL","9792.KL","5107.KL","8605.KL","0157.KL","5022.KL","5066.KL","0250.KL","9946.KL","5025.KL","5295.KL","7243.KL","7089.KL"]
consumer_list_2 = ["3514.KL","5079.KL","7209.KL","3018.KL","5157.KL","9113.KL","8532.KL","8885.KL","7184.KL","7080.KL","5156.KL","7084.KL","3859.KL","4219.KL","5305.KL","5908.KL","5265.KL","7722.KL","5250.KL","0049.KL","5187.KL","1481.KL","7215.KL","7154.KL","2097.KL","9423.KL","4081.KL","8966.KL","7128.KL","0136.KL","5196.KL","8672.KL","3891.KL","6203.KL","5346.KL","5260.KL","5081.KL","5592.KL","7139.KL","8303.KL","0229.KL","7200.KL","7203.KL","7202.KL","6068.KL","8079.KL","5300.KL","7935.KL","7149.KL","5275.KL","5318.KL","3255.KL"]

# 补漏清单 —— 这90支存在于STOCK_NAMES对照表,但当初分12板块时漏收(2026-08-19补上)
# 包含GENTING/NESTLE/SIME/TM/AXIATA/ASTRO/MAXIS/DLADY/CARLSBG/PPB等蓝筹在内
# 注:'5235SS.KL' 是 '5235.KL'(KLCC) 的重复/无效代号,yfinance查不到,故不补入
missing_list = ["0012.KL","0032.KL","0037.KL","0059.KL","0082.KL","0159.KL","0172.KL","0180.KL","0183.KL","0217.KL","0239.KL","1562.KL","1619.KL","2755.KL","2836.KL","3026.KL","3182.KL","3301.KL","3719.KL","3905.KL","4065.KL","4197.KL","4405.KL","4502.KL","4707.KL","4863.KL","5008.KL","5016.KL","5024.KL","5031.KL","5080.KL","5090.KL","5099.KL","5104.KL","5160.KL","5166.KL","5188.KL","5238.KL","5242.KL","5247.KL","5248.KL","5252.KL","5278.KL","5306.KL","5316.KL","5326.KL","5332.KL","5335.KL","5337.KL","5351.KL","5533.KL","5649.KL","5657.KL","5983.KL","6012.KL","6084.KL","6351.KL","6399.KL","6432.KL","6888.KL","6939.KL","6947.KL","7006.KL","7031.KL","7035.KL","7060.KL","7062.KL","7085.KL","7088.KL","7103.KL","7107.KL","7134.KL","7167.KL","7180.KL","7223.KL","7230.KL","7234.KL","7246.KL","7252.KL","7412.KL","7439.KL","7668.KL","7757.KL","8478.KL","9172.KL","9385.KL","9431.KL","9776.KL","9997.KL"]

TICKERS = sorted(set(
    industrial_list_1 + industrial_list_2 + industrial_list_3 + industrial_list_4 +
    energy_list + healthcare_list + transport_list + utilities_list +
    tech_list + reit_list + construction_list + finance_list +
    plantation_list + property_list_1 + property_list_2 +
    consumer_list_1 + consumer_list_2 + missing_list
))


def clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=['Close'])


def resample_ohlcv(df, rule):
    agg = pd.DataFrame({
        'Open': df['Open'].resample(rule).first(),
        'High': df['High'].resample(rule).max(),
        'Low': df['Low'].resample(rule).min(),
        'Close': df['Close'].resample(rule).last(),
        'Volume': df['Volume'].resample(rule).sum(),
    })
    return agg.dropna(subset=['Close'])


def calc_rsi_wilder(close, length):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def calc_mcdx_series(close):
    idx = close.index
    rb = calc_rsi_wilder(close, BANKER_PERIOD).to_numpy()
    rh = calc_rsi_wilder(close, HOT_PERIOD).to_numpy()

    banker = np.clip(BANKER_SENS * (rb - BANKER_BASE), 0.0, 20.0)
    hot = np.clip(HOT_SENS * (rh - HOT_BASE), 0.0, 20.0)
    retail = np.clip(20.0 - np.maximum(banker, hot), 0.0, 20.0)

    dominant = np.full(len(idx), -1)
    is_bank = (banker >= MEDIUM_TH) & (banker >= hot) & (banker >= retail)
    is_hot = (~is_bank) & (hot >= MEDIUM_TH) & (hot >= banker) & (hot >= retail)
    is_ret = (~is_bank) & (~is_hot) & (retail >= MEDIUM_TH) & (retail >= banker) & (retail >= hot)
    dominant[is_bank] = 0
    dominant[is_hot] = 1
    dominant[is_ret] = 2

    dom_value = np.zeros(len(idx))
    dom_value[is_bank] = banker[is_bank]
    dom_value[is_hot] = hot[is_hot]
    dom_value[is_ret] = retail[is_ret]

    lvl_strong = dom_value >= STRONG_TH
    lvl_medium = (dom_value >= MEDIUM_TH) & (dom_value < STRONG_TH)

    mcdx_score = np.zeros(len(idx))
    m0 = dominant == 0
    mcdx_score[m0 & lvl_strong] = 100.0
    mcdx_score[m0 & lvl_medium] = 70.0
    mcdx_score[m0 & ~lvl_strong & ~lvl_medium] = 40.0
    m1 = dominant == 1
    mcdx_score[m1 & lvl_strong] = 85.0
    mcdx_score[m1 & lvl_medium] = 60.0
    mcdx_score[m1 & ~lvl_strong & ~lvl_medium] = 30.0
    m2 = dominant == 2
    mcdx_score[m2 & lvl_strong] = -90.0
    mcdx_score[m2 & lvl_medium] = -55.0
    mcdx_score[m2 & ~lvl_strong & ~lvl_medium] = -20.0

    return (pd.Series(dominant, index=idx), pd.Series(mcdx_score, index=idx))


def analyze_timeframe_last(df, min_len):
    if len(df) < min_len:
        return None
    dom, score = calc_mcdx_series(df['Close'])
    val = score.iloc[-1]
    if pd.isna(val):
        return None
    return float(val)


def compute_resonance_score(daily_df):
    if len(daily_df) < _MIN_TF_LEN:
        return -999.0
    weekly = resample_ohlcv(daily_df, 'W')
    monthly = resample_ohlcv(daily_df, 'ME')

    d = analyze_timeframe_last(daily_df, _MIN_TF_LEN)
    w = analyze_timeframe_last(weekly, _MIN_TF_LEN)
    m = analyze_timeframe_last(monthly, _MIN_TF_LEN)

    vals = [v for v in (d, w, m) if v is not None]
    if len(vals) < 3:
        return -999.0
    return float(min(vals))


def compute_persistence(daily_df, months=PERSIST_WINDOW_MONTHS):
    monthly = resample_ohlcv(daily_df, 'ME')
    if len(monthly) < _MIN_TF_LEN:
        return None, 0

    dom, _ = calc_mcdx_series(monthly['Close'])
    dom_valid = dom[dom != -1]
    if len(dom_valid) == 0:
        return None, 0

    recent = dom_valid.tail(months)
    if len(recent) == 0:
        return None, 0

    is_red = (recent == 0)
    red_ratio = float(is_red.mean())

    streak = 0
    for v in reversed(is_red.tolist()):
        if v:
            streak += 1
        else:
            break

    return red_ratio, streak


def main():
    print("=" * 95)
    print(f"📊 全马股甜蜜点扫描 (共{len(TICKERS)}支)  |  "
          f"共振>={RESONANCE_TH} + 强势持续度{RED_LOW}~{RED_HIGH}")
    print(f"   {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  |  period={PERIOD}(锁定)")
    print("=" * 95)

    buy_list, watch_list = [], []
    skipped = []
    start_time = datetime.datetime.now()

    for i, tk in enumerate(TICKERS):
        if (i + 1) % 30 == 0 or i == len(TICKERS) - 1:
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            avg = elapsed / (i + 1)
            remaining = avg * (len(TICKERS) - i - 1)
            print(f"  处理中... {i+1}/{len(TICKERS)}  已用时{elapsed:.0f}秒  预计还需{remaining:.0f}秒")

        try:
            df = clean(yf.download(tk, period=PERIOD, auto_adjust=True, progress=False))
            if len(df) < _MIN_TF_LEN + 60:
                skipped.append((tk, "数据不足"))
                continue

            res = compute_resonance_score(df)
            rr, streak = compute_persistence(df)

            if rr is None:
                skipped.append((tk, "月线历史不足5年"))
                continue

            resonance_ok = res >= RESONANCE_TH
            sweet_ok = RED_LOW <= rr <= RED_HIGH

            if resonance_ok and sweet_ok:
                buy_list.append((tk, res, rr, streak))
            elif resonance_ok and rr > WARN_HIGH:
                watch_list.append((tk, res, rr, streak))

        except Exception as e:
            skipped.append((tk, str(e)[:40]))

    print("\n" + "=" * 95)
    print(f"🟢 甜蜜点买入清单(全马股版, {len(buy_list)} 支)—— 回测胜率63.6%,中位超额3.43%")
    print("=" * 95)
    if buy_list:
        for tk, res, rr, streak in sorted(buy_list, key=lambda x: -x[1]):
            name = STOCK_NAMES.get(tk, "")
            print(f"  {tk:<10} {name:<10} 共振{res:.0f}  强势持续度{rr:.2f}  连续{streak}月")
    else:
        print("  今天没有股票落在甜蜜点。宁缺勿滥。")

    if watch_list:
        print(f"\n🟡 满仓警惕清单(全马股版, {len(watch_list)} 支)—— 共振够但已到极端强势区,历史上表现最弱")
        for tk, res, rr, streak in sorted(watch_list, key=lambda x: -x[2]):
            name = STOCK_NAMES.get(tk, "")
            print(f"  {tk:<10} {name:<10} 共振{res:.0f}  强势持续度{rr:.2f}(>{WARN_HIGH})")

    print(f"\n跳过 {len(skipped)} 支")
    print("\n提醒:强势持续度不是庄家持仓比例，是RSI50/RSI40同时超阈值的月份占比。")
    print("      0.85是警戒线不是铁律，别机械一刀切。")

    rows = [(datetime.datetime.now().strftime('%Y-%m-%d'), tk, STOCK_NAMES.get(tk, ""), res, rr, streak, '甜蜜点')
            for tk, res, rr, streak in buy_list]
    rows += [(datetime.datetime.now().strftime('%Y-%m-%d'), tk, STOCK_NAMES.get(tk, ""), res, rr, streak, '满仓警惕')
             for tk, res, rr, streak in watch_list]
    out_df = pd.DataFrame(rows, columns=['记录日', '股票', '名字', '共振', '强势持续度', '连续月', '分类'])
    fname = f"all_klse_sweetspot_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
    out_df.to_csv(fname, index=False, encoding='utf-8-sig')
    print(f"\n📝 已存档: {fname}")


if __name__ == "__main__":
    main()
