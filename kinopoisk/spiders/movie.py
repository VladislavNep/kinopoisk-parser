import random
from fake_useragent import UserAgent
import scrapy
from scrapy.loader.processors import Join
from kinopoisk.tormanager import ConnectionManager
from kinopoisk.items import MovieItem, MovieLoader, MovieIdItem, MovieIdLoader, PersonIdItem, PersonIdLoader
from inline_requests import inline_requests


class MovieSpider(scrapy.Spider):
    """
    :ivar: start_url
    :returns: {
    title: str,
    description: str,
    poster: file_path,
    trailer: url,
    country: str,
    directors: [],
    actors: [],
    world_premiere: str,
    budget: int,
    fees_in_usa: int,
    fees_in_world: int,
    rating_kp: float,
    rating_imdb: float,
    movie_shots: [file_path],
    }
    """
    name = "movie"
    custom_settings = {
        'ITEM_PIPELINES': {
            'scrapy.pipelines.images.ImagesPipeline': 1,
            'kinopoisk.pipelines.PostersPipeline': 310,
            'kinopoisk.pipelines.MovieShotsPipeline': 300,
        },

        "DOWNLOAD_DELAY": 5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CONCURRENT_REQUESTS": 2,
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_url = 'https://www.kinopoisk.ru/popular/?quick_filters=films&tab=all'
        self.cm = ConnectionManager('891vnp505')
        self.BASE_URL = 'https://www.kinopoisk.ru'
        self.css = {
            'movie_items': 'div.selection-list > div.desktop-rating-selection-film-item',
            'title': '.moviename-title-wrapper::text',
            'movie_link': 'a.selection-film-item-meta__link::attr(href)',
            'movie_info': 'div.movie-info__table-container>#infoTable>table#info',
            'actors': 'div.movie-info__table-container>#actorList ul',
            'world_premier': '#div_world_prem_td2 > div:nth-child(1) > a::text',
            'rf_premiere': '.rel-date_description > span:nth-child(2) > a::text',
            'country': 'table.info > tr:nth-child(2) > td:nth-child(2) > div:nth-child(1) > a::text',
            'budget1': '.en > td.dollar a::text',
            'budget2': '.en > td.dollar ::text',
            'description': '.film-synopsys::text',
            'time': '#runtime::text',
            'fees_in_usa': '#div_usa_box_td2 > div:nth-child(1) > a::text',
        }
        self.xpath = {
            'directors': './/td[@itemprop="director"]/a/text()',
            'director_id': './/td[@itemprop="director"]/a/@href',
            'genre': './/td[2]/span[@itemprop="genre"]/a/text()',
            'rating_kp': './/meta[@itemprop="ratingValue"]/@content',
            'imdb': './/div[@id="block_rating"]//div[@class="block_2"]//div[last()]/text()',
            'imdb2': './/div[@id="block_rating"]//div[@class="block_2"]//div[last()-1]/text()',
            'trailer_id': './/*[@id="movie-trailer-block"]/@data-trailer-id',
        }

    def start_requests(self):
        yield scrapy.Request(
            url=self.start_url,
            headers={
                    'User-Agent': UserAgent().random,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Referer': 'www.kinopoisk.ru',
                    'Host': 'www.kinopoisk.ru'
                },
            callback=self.parse,
            meta=dict(proxy='127.0.0.1:8118')
        )

    def parse(self, response, i=1):
        _count_req = 0
        print(f"Парсинг {i} страницы из {self.get_count_page(response)}")
        loader_movid = MovieIdLoader(item=MovieIdItem())
        for movie_item in response.css(self.css['movie_items']):
            _count_req += 1
            if _count_req >= 30:
                self.cm.new_identity()
                _count_req = 0

            movie_id = movie_item.css(self.css['movie_link']).re_first(r'([0-9]\d*)')
            loader_movid.add_value('movie_id', int(movie_id))

            yield response.follow(
                url=f'/film/{movie_id}',
                callback=self.get_movie_info,
                headers={
                    'User-Agent': UserAgent().random,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Referer': response.url,
                    'Host': 'www.kinopoisk.ru'
                },
                cb_kwargs=dict(movie_id=movie_id),
                meta=dict(proxy='127.0.0.1:8118')
            )

        if self.get_next_page(response) is not None:
            i += 1
            yield response.follow(
                url=self.get_next_page(response),
                callback=self.parse,
                headers={
                    'User-Agent': UserAgent().random,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Referer': response.url,
                    'Host': 'www.kinopoisk.ru'
                },
                cb_kwargs=dict(i=i),
                meta=dict(proxy='127.0.0.1:8118')
            )

        yield loader_movid.load_item()

    def get_movie_info(self, response, movie_id):
        loader_inf = MovieLoader(item=MovieItem(), response=response)
        loader_inf.add_css('title', self.css['title'])
        loader_inf.add_xpath('rating_kp', self.xpath['rating_kp'])
        loader_inf.add_css('world_premier', self.css['world_premier'], re=r'^[а-яА-ЯёЁ0-9\s]+$')
        loader_inf.add_css('rf_premiere', self.css['world_premier'], re=r'^[а-яА-ЯёЁ0-9\s]+$')
        loader_inf.add_css('country', self.css['country'])
        loader_inf.add_xpath('directors', self.xpath['directors'])
        loader_inf.add_xpath('genre', self.xpath['genre'])
        loader_inf.add_css('fees_in_usa', self.css['fees_in_usa'], Join(separator=''), re=r'([0-9]\d*)')
        loader_inf.add_css('time', self.css['time'], re=r'([0-9]\d*)')
        loader_inf.add_css('description', self.css["description"])

        imdb = response.xpath(self.xpath['imdb']).re_first(r'^IMDb: ([0-9.]+) \(([0-9 ]+)\)$')
        if not imdb:
            imdb = response.xpath(self.xpath['imdb2']).re_first(r'^IMDb: ([0-9.]+) \(([0-9 ]+)\)$')
        if imdb:
            loader_inf.add_value('rating_imdb', imdb)

        trailer_id = response.xpath(self.xpath['trailer_id']).get()
        trailer = f'https://widgets.kinopoisk.ru/discovery/trailer/{trailer_id}?onlyPlayer=1&autoplay=0&cover=1'
        loader_inf.add_value('trailer', trailer)

        # бюджет и сборы в $
        budget = ''.join(
            response.css(self.css['budget1']).re(r'([0-9]\d*)') or response.css(self.css['budget2']).re(r'([0-9]\d*)'))
        loader_inf.add_value('budget', budget)

        fees_in_world_str = ''.join(
            response.xpath('//td[@id="div_world_box_td2"]/div[1]/a[1]/text()').re(r'([0-9=]\d*)') or response.xpath(
                '//tr[14]/td[@class="dollar" and 2]/div[1]/a[1]').re(r'([0-9=]\d*)'))
        fees_in_world = fees_in_world_str[fees_in_world_str.rfind('=') + 1:]
        loader_inf.add_value('fees_in_world', fees_in_world)

        # вытаскиваем актеров
        if response.css(self.css['actors']):
            actors_name = response.css(self.css['actors'])[0].css('li>a::text')[:5].getall()
            loader_inf.add_value('actors', actors_name)

        # вытаскиваем постер фильма для скачивания
        poster_url = self.BASE_URL + f'/images/film_big/{movie_id}.jpg'
        loader_inf.add_value('poster_url', poster_url)

        # вытаскиваем movie shots
        yield response.follow(
            url=self.BASE_URL + f'/film/{movie_id}/stills',
            callback=self.movie_shots,
            headers={
                'User-Agent': UserAgent().random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                'Referer': response.url,
                'Host': 'www.kinopoisk.ru'
            },
            meta={
                'loader': loader_inf,
                'proxy': '127.0.0.1:8118'
            }
        )

        # вытаскиваем все id людей для дальнейшего использования
        yield self.get_person_id(response)

    def get_person_id(self, response):
        loader_per = PersonIdLoader(item=PersonIdItem(), response=response)
        loader_per.add_xpath('person_id', self.xpath['director_id'], re=r'([0-9]\d*)')

        if response.css(self.css['actors']):
            actors_id = response.css(self.css['actors'])[0].css('li>a::attr(href)')[:5].re(r'([0-9]\d*)')
            loader_per.add_value('person_id', actors_id)

        return loader_per.load_item()

    @inline_requests
    def movie_shots(self, response):
        loader_inf = response.meta['loader']
        urls = response.css('table.js-rum-hero > tr > td > a::attr(href)')[:9].getall()
        for url in urls:
            res = yield response.follow(
                url=response.urljoin(url),
                headers={
                    'User-Agent': UserAgent().random,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Referer': response.url,
                    'Host': 'www.kinopoisk.ru'
                },
                meta=dict(proxy='127.0.0.1:8118')
            )

            loader_inf.add_value('movie_shot_urls', res.css('img#image::attr(src)').get())

        yield loader_inf.load_item()

    @staticmethod
    def get_next_page(response):
        content_url = response.css('div.paginator>a.paginator__page-relative::text')[-1].get() == ('Вперёд' or 'Next')
        url = response.css('div.paginator>a.paginator__page-relative::attr(href)')[-1].get()
        return response.urljoin(url) if content_url else None

    @staticmethod
    def get_count_page(response):
        return response.css('div.paginator a.paginator__page-number::text')[-1].get()
