#include "site.hpp"

#include <iostream>
#include <cstring>
#include <ctype.h>

using namespace std;  

class Number
{
  public:
    int n;
  
  Number(int set_n)
  {
    n = set_n;
  }

  Number operator+(const Number& num)
  {
    return Number(this->n + num.n);
  }
};


int main(int argc, char** argv)
{

  Number a(5);
  Number b(7);

  Number c = a + b;

  cout << c.n;



  return 0;
}