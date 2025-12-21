#ifndef SITE_HPP
#define SITE_HPP

#include <string> 

class Site {
private:
    long id;
    std::string name;
    std::string street;
    std::string city;
    std::string state;
    std::string zip;

public:
    bool is_valid();

    Site(std::string city);

    std::string get_city()
    {
        return city;
    }
};

#endif
