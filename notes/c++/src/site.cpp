
#include "site.hpp" 

Site::Site(std::string new_city) {
    city = new_city;
    //...
}

bool Site::is_valid() {
    return !city.empty();
}
