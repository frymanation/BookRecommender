def writemissing(title,bm):
    if(bm=='book'):
        with open('missingbook.csv','a') as f:
            f.write(title)
