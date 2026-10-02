from latin_macronizer.macronizer import Macronizer

def main():
    # Initialize the macronizer
    mac = Macronizer()
    
    # Add your test data and breakpoints here
    test_text = "puella puellam amat"
    texttomacronize = "Lithkwkj. Castra sunt in Italia contra populum Romanum in Etruriae faucibus conlocata, crescit in dies singulos hostium numerus; eorum autem castrorum imperatorem ducemque hostium intra moenia atque adeo in senatu videtis intestinam aliquam cotidie perniciem rei publicae molientem. Si te iam, Catilina, comprehendi, si interfici iussero, credo, erit verendum mihi, ne non potius hoc omnes boni serius a me quam quisquam crudelius factum esse dicat. Verum ego hoc, quod iam pridem factum esse oportuit, certa de causa nondum adducor ut faciam. Tum denique interficiere, cum iam nemo tam inprobus, tam perditus, tam tui similis inveniri poterit, qui id non iure factum esse fateatur."

    mac.settext(texttomacronize)
    macronizedtext = mac.gettext(domacronize=True, alsomaius=False, performutov=True, performitoj=True, markambigs=True, confidence_threshold=0.8, output_format="inline")
    
    print("Result:", macronizedtext)

if __name__ == "__main__":
    main()